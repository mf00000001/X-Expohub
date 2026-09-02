"""
V2.2: 增长引擎 — 签到 + 邀请 + 展商信誉
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.base import get_db
from app.models.user import User
from app.models.checkin import CheckIn
from app.models.points import PointsLedger
from app.models.membership import Membership, TIER_PRODUCT_LIMITS
from app.core.deps import get_current_active_user
from app.core.exceptions import BadRequest, NotFound

router = APIRouter(prefix="/growth", tags=["增长"])


# ============================================================
# 每日签到
# ============================================================

@router.post("/checkin")
def checkin(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """每日签到领积分"""
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 检查今天是否已签到
    existing = db.query(CheckIn).filter(
        CheckIn.user_id == current_user.id,
        CheckIn.created_at >= today,
    ).first()
    if existing:
        raise BadRequest(message="今日已签到，明天再来吧！连续签到" + str(existing.streak) + "天")

    # 计算连续签到天数
    yesterday = today - timedelta(days=1)
    last = db.query(CheckIn).filter(
        CheckIn.user_id == current_user.id,
        CheckIn.created_at >= yesterday,
        CheckIn.created_at < today,
    ).first()

    streak = (last.streak + 1) if last else 1

    # 计算积分：基础2分 + 连续签到奖励
    bonus = min(streak // 7, 4) * 5  # 每连续7天+5，最多+20
    points = 2 + bonus

    # 连续7天额外奖励
    extra_msg = ""
    if streak == 7:
        points += 20
        extra_msg = " 🔥连续7天额外+20分！"
    elif streak == 30:
        points += 50
        extra_msg = " 👑连续30天额外+50分！"

    checkin = CheckIn(user_id=current_user.id, streak=streak, points_earned=points)
    db.add(checkin)

    # 加积分
    current_user.total_points = (current_user.total_points or 0) + points
    ledger = PointsLedger(
        user_id=current_user.id,
        transaction_type="earn_browse",
        amount=points,
        balance_after=current_user.total_points,
        description=f"📅 签到第{streak}天 +{points}分" + extra_msg,
    )
    db.add(ledger)
    db.commit()

    return {
        "success": True, "code": "OK",
        "message": f"签到成功！连续签到{streak}天，+{points}分" + extra_msg,
        "data": {"streak": streak, "points_earned": points, "balance": current_user.total_points},
    }


@router.get("/checkin/status")
def checkin_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """查询今日是否已签到"""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    existing = db.query(CheckIn).filter(
        CheckIn.user_id == current_user.id,
        CheckIn.created_at >= today,
    ).first()
    last = db.query(CheckIn).filter(
        CheckIn.user_id == current_user.id
    ).order_by(CheckIn.created_at.desc()).first()

    return {
        "success": True, "code": "OK",
        "data": {
            "checked_in_today": existing is not None,
            "streak": existing.streak if existing else (last.streak if last else 0),
            "today_points": existing.points_earned if existing else 0,
        }
    }


# ============================================================
# 邀请裂变
# ============================================================

class ReferralRequest(BaseModel):
    referral_code: str


@router.post("/referral/apply")
def apply_referral(
    data: ReferralRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """被邀请人填写邀请码"""
    if current_user.referred_by:
        raise BadRequest(message="您已被邀请过，不能重复使用邀请码")

    inviter = db.query(User).filter(User.referral_code == data.referral_code).first()
    if not inviter:
        raise NotFound(message="邀请码无效")
    if inviter.id == current_user.id:
        raise BadRequest(message="不能邀请自己")

    current_user.referred_by = inviter.id

    # 双方各得100积分
    now = datetime.now(timezone.utc)
    for u, desc in [(current_user, "👥 接受邀请 +100分"), (inviter, "👥 邀请新用户 +100分")]:
        u.total_points = (u.total_points or 0) + 100
        db.add(PointsLedger(
            user_id=u.id, transaction_type="earn_registration",
            amount=100, balance_after=u.total_points, description=desc,
        ))

    db.commit()
    return {
        "success": True, "code": "OK",
        "message": f"邀请成功！你和邀请人各获得100积分",
        "data": {"inviter": inviter.nickname or inviter.username, "points": 100},
    }


@router.get("/referral/my-code")
def my_referral_code(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """我的邀请码和邀请统计"""
    # 统计被邀请人数
    count = db.query(func.count(User.id)).filter(
        User.referred_by == current_user.id
    ).scalar() or 0

    return {
        "success": True, "code": "OK",
        "data": {
            "referral_code": current_user.referral_code or "",
            "invited_count": count,
            "message": f"邀请好友注册，双方各得100积分！你的邀请码：{current_user.referral_code}",
        }
    }


# ============================================================
# 展商信誉等级
# ============================================================

EXHIBITOR_TIERS = [
    {"tier": "bronze", "label": "🥉 铜牌展商", "min_score": 0},
    {"tier": "silver", "label": "🥈 银牌展商", "min_score": 50},
    {"tier": "gold", "label": "🥇 金牌展商", "min_score": 200},
    {"tier": "diamond", "label": "💎 钻石展商", "min_score": 500},
]


def calculate_exhibitor_score(user_id: int, db: Session) -> int:
    """计算展商信誉分"""
    from app.models.product import Product
    from app.models.booth import Booth
    from app.models.micro_booth import MicroBooth
    from app.models.analytics import AnalyticsEvent
    from app.models.procurement_match import ProcurementMatch

    score = 0

    # 资料完善度
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        if user.company: score += 10
        if user.bio: score += 10
        if user.avatar_url: score += 10
        if user.industry_domain: score += 10
        if user.phone: score += 5

    # 展品数
    product_count = db.query(func.count(Product.id)).filter(Product.exhibitor_id == user_id).scalar() or 0
    score += product_count * 3

    # 展位数
    booth_count = db.query(func.count(Booth.id)).filter(Booth.exhibitor_id == user_id).scalar() or 0
    score += booth_count * 15

    # 浏览量
    view_count = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == user_id,
        AnalyticsEvent.event_type == "page_view",
    ).scalar() or 0
    score += view_count // 10

    # 收藏数
    fav_count = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == user_id,
        AnalyticsEvent.event_type == "favorite",
    ).scalar() or 0
    score += fav_count * 3

    # 采购匹配成功数
    match_count = db.query(func.count(ProcurementMatch.id)).filter(
        ProcurementMatch.exhibitor_id == user_id,
        ProcurementMatch.is_accepted == True,
    ).scalar() or 0
    score += match_count * 20

    return score


def get_tier_from_score(score: int) -> str:
    """根据分数获取等级"""
    tier = "bronze"
    for t in reversed(EXHIBITOR_TIERS):
        if score >= t["min_score"]:
            tier = t["tier"]
            break
    return tier


@router.get("/tier")
def my_tier(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """查询当前用户信誉等级（展商专用）"""
    if current_user.role not in ("exhibitor", "admin", "organizer"):
        return {"success": True, "code": "OK", "data": {"tier": None, "score": 0, "message": "仅展商有信誉等级"}}

    score = calculate_exhibitor_score(current_user.id, db)
    tier = get_tier_from_score(score)
    tier_info = next((t for t in EXHIBITOR_TIERS if t["tier"] == tier), EXHIBITOR_TIERS[0])
    next_tier = next((t for t in EXHIBITOR_TIERS if t["min_score"] > score), None)

    # 更新用户等级
    if current_user.exhibitor_tier != tier:
        current_user.exhibitor_tier = tier
        db.commit()

    return {
        "success": True, "code": "OK",
        "data": {
            "tier": tier,
            "label": tier_info["label"],
            "score": score,
            "next_tier": next_tier["label"] if next_tier else None,
            "points_to_next": (next_tier["min_score"] - score) if next_tier else 0,
            "factors": {
                "products": "每个展品+3分",
                "booths": "每个展位+15分",
                "views": "每10次浏览+1分",
                "favorites": "每个收藏+3分",
                "matches": "每次成功匹配+20分",
            },
        },
    }
