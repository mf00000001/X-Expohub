"""
V2.2: 商业积分 API
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.base import get_db
from app.models.user import User
from app.models.points import PointsLedger, POINTS_RULES, REDEEM_CATALOG
from app.api.deps import get_current_active_user
from app.core.exceptions import BadRequest, NotFound

router = APIRouter(prefix="/points", tags=["积分"])


class RedeemRequest(BaseModel):
    catalog_id: int


@router.get("/balance")
def balance(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """积分余额 + 今日获得"""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_earned = db.query(func.coalesce(func.sum(PointsLedger.amount), 0)).filter(
        PointsLedger.user_id == current_user.id,
        PointsLedger.amount > 0,
        PointsLedger.created_at >= today,
    ).scalar() or 0

    return {
        "success": True, "code": "OK", "data": {
            "balance": current_user.total_points,
            "today_earned": today_earned,
        }
    }


@router.get("/daily-stats")
def daily_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """今日各类型已获得积分情况"""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    result = {}
    for rule_key, rule in POINTS_RULES.items():
        earned = db.query(func.coalesce(func.sum(PointsLedger.amount), 0)).filter(
            PointsLedger.user_id == current_user.id,
            PointsLedger.transaction_type == rule_key,
            PointsLedger.created_at >= today,
        ).scalar() or 0
        result[rule_key] = {
            "label": rule["label"],
            "per_action": rule["amount"],
            "daily_cap": rule["daily_cap"],
            "today_earned": earned,
            "remaining": max(0, rule["daily_cap"] - (earned // rule["amount"])),
        }

    return {"success": True, "code": "OK", "data": result}


@router.get("/history")
def history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """积分明细"""
    q = db.query(PointsLedger).filter(PointsLedger.user_id == current_user.id)
    total = q.count()
    items = q.order_by(PointsLedger.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()

    return {
        "success": True, "code": "OK", "data": {
            "list": [{
                "id": i.id, "type": i.transaction_type, "amount": i.amount,
                "balance_after": i.balance_after, "description": i.description,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            } for i in items],
            "total": total, "page": page, "pageSize": page_size,
            "totalPages": (total + page_size - 1)//page_size if page_size else 0,
        }
    }


@router.get("/catalog")
def catalog():
    """兑换目录"""
    return {"success": True, "code": "OK", "data": REDEEM_CATALOG}


@router.post("/redeem")
def redeem(
    data: RedeemRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """兑换商品"""
    item = next((r for r in REDEEM_CATALOG if r["id"] == data.catalog_id), None)
    if not item:
        raise NotFound(message="商品不存在")

    if current_user.total_points < item["points"]:
        raise BadRequest(message=f"积分不足，需要{item['points']}分，当前{current_user.total_points}分")

    # 扣积分
    current_user.total_points -= item["points"]
    ledger = PointsLedger(
        user_id=current_user.id,
        transaction_type=f"redeem_{item['name']}",
        amount=-item["points"],
        balance_after=current_user.total_points,
        description=f"兑换：{item['name']}",
    )
    db.add(ledger)
    db.commit()

    return {
        "success": True, "code": "OK",
        "message": f"成功兑换{item['name']}！消耗{item['points']}积分",
        "data": {"balance": current_user.total_points},
    }


# ============================================================
# 积分赚取（内部调用）
# ============================================================

def earn_points(user_id: int, transaction_type: str, reference_type: str, reference_id: int, db: Session) -> dict:
    """给用户加积分，检查每日上限"""
    rule = POINTS_RULES.get(transaction_type)
    if not rule:
        return {"success": False, "message": "未知积分类型"}

    # 检查每日上限
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_earned = db.query(func.coalesce(func.sum(PointsLedger.amount), 0)).filter(
        PointsLedger.user_id == user_id,
        PointsLedger.transaction_type == transaction_type,
        PointsLedger.created_at >= today,
    ).scalar() or 0

    if today_earned >= rule["daily_cap"]:
        return {"success": False, "message": f"今日{rule['label']}积分已达上限({rule['daily_cap']})"}

    # 查找用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "用户不存在"}

    # 加积分
    amount = rule["amount"]
    user.total_points = (user.total_points or 0) + amount
    ledger = PointsLedger(
        user_id=user_id,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=user.total_points,
        reference_type=reference_type,
        reference_id=reference_id,
        description=f"{rule['label']} +{amount}分",
    )
    db.add(ledger)
    db.commit()

    return {"success": True, "earned": amount, "balance": user.total_points}
