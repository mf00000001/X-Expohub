"""
管理后台路由（Admin / Dashboard）

前端 admin.ts 期望路由前缀 /admin

端点（仅 admin / organizer 可访问）：
- GET /admin/stats                   总览统计
- GET /admin/stats/overview          综合统计概览
- GET /admin/stats/users/growth      用户增长趋势
- GET /admin/stats/exhibitions/trend 展会趋势
- GET /admin/stats/exhibitions       展会统计
- GET /admin/stats/exhibitors        展商统计
- GET /admin/stats/procurements      采购统计

管理端点（桩）：
- GET /admin/teams                   团队列表（桩）
- GET /admin/users                   用户列表（桩）
- GET /admin/approvals               审批列表（桩）
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.base import get_db
from app.models.user import User
from app.models.exhibition import Exhibition
from app.models.booth import Booth
from app.models.product import Product
from app.models.procurement import Procurement
from app.models.message import Message
from app.core.deps import get_current_active_user
from app.core.exceptions import Forbidden

router = APIRouter(prefix="/admin", tags=["管理后台"])


# ============================================================
# 辅助函数
# ============================================================

def _require_admin_or_organizer(current_user: User) -> None:
    """要求当前用户角色为 admin 或 organizer，否则抛出 Forbidden"""
    if current_user.role not in ("admin", "organizer"):
        raise Forbidden(message="仅管理员或主办方可访问")
    # 主办方必须已通过入驻审核（pending/rejected 均不可执行管理操作）
    if current_user.role == "organizer" and current_user.organizer_status != "approved":
        raise Forbidden(message="主办方入驻审核未通过，无法执行管理操作")


def _count_by_status(db: Session, model) -> dict:
    """统计某模型各状态的记录数，返回 {status: count} 字典"""
    rows = db.query(model.status, func.count(model.id)).group_by(model.status).all()
    return {status: count for status, count in rows}


def _ok(data) -> dict:
    """统一成功响应"""
    return {"success": True, "code": "OK", "message": "获取成功", "data": data}


# ============================================================
# 统计端点
# ============================================================

@router.get("/stats")
def get_overview_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """总览统计 — 系统核心指标汇总（兼容旧前端 /admin/stats）"""
    _require_admin_or_organizer(current_user)

    total_exhibitions = db.query(func.count(Exhibition.id)).scalar() or 0
    total_booths = db.query(func.count(Booth.id)).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0
    total_procurements = db.query(func.count(Procurement.id)).scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_messages = db.query(func.count(Message.id)).scalar() or 0

    exhibitions_by_status = _count_by_status(db, Exhibition)
    booths_by_status = _count_by_status(db, Booth)

    return _ok({
        "total_exhibitions": total_exhibitions,
        "total_booths": total_booths,
        "total_products": total_products,
        "total_procurements": total_procurements,
        "total_users": total_users,
        "total_messages": total_messages,
        "exhibitions_by_status": exhibitions_by_status,
        "booths_by_status": booths_by_status,
    })


@router.get("/stats/overview")
def get_stats_overview(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """综合统计概览

    前端 admin.ts StatsOverview 接口：
    total_users, total_exhibitions, total_booths, total_registrations,
    total_procurements, total_products, total_messages,
    user_role_distribution, exhibition_status_distribution,
    procurement_status_distribution, exhibitor_active_count,
    exhibitor_with_booth_count, exhibitor_with_product_count,
    procurement_total, procurement_matched, procurement_match_rate
    """
    _require_admin_or_organizer(current_user)

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_exhibitions = db.query(func.count(Exhibition.id)).scalar() or 0
    total_booths = db.query(func.count(Booth.id)).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0
    total_procurements = db.query(func.count(Procurement.id)).scalar() or 0
    total_messages = db.query(func.count(Message.id)).scalar() or 0

    # 用户角色分布
    role_rows = db.query(User.role, func.count(User.id)).group_by(User.role).all()
    user_role_distribution = {role: count for role, count in role_rows}

    # 展会状态分布
    exhibition_status_distribution = _count_by_status(db, Exhibition)

    # 采购状态分布
    procurement_status_distribution = _count_by_status(db, Procurement)

    # 展商相关统计
    exhibitor_active_count = (
        db.query(func.count(User.id))
        .filter(User.role == "exhibitor", User.status == "active")
        .scalar()
    ) or 0

    exhibitor_ids = db.query(User.id).filter(User.role == "exhibitor").subquery()
    exhibitor_with_booth_count = (
        db.query(func.count(func.distinct(Booth.exhibitor_id)))
        .filter(Booth.exhibitor_id.in_(exhibitor_ids))
        .scalar()
    ) or 0
    exhibitor_with_product_count = (
        db.query(func.count(func.distinct(Product.exhibitor_id)))
        .filter(Product.exhibitor_id.in_(exhibitor_ids))
        .scalar()
    ) or 0

    # 采购匹配统计
    procurement_total = total_procurements
    procurement_matched = (
        db.query(func.count(Procurement.id))
        .filter(Procurement.status == "matched")
        .scalar()
    ) or 0
    procurement_match_rate = (
        round(procurement_matched / procurement_total * 100, 1)
        if procurement_total > 0
        else 0.0
    )

    # 注册数（暂用展会总数代替，后续可扩展 Registration 表）
    total_registrations = 0  # TODO: 接入 Registration 表

    return _ok({
        "total_users": total_users,
        "total_exhibitions": total_exhibitions,
        "total_booths": total_booths,
        "total_registrations": total_registrations,
        "total_procurements": total_procurements,
        "total_products": total_products,
        "total_messages": total_messages,
        "user_role_distribution": user_role_distribution,
        "exhibition_status_distribution": exhibition_status_distribution,
        "procurement_status_distribution": procurement_status_distribution,
        "exhibitor_active_count": exhibitor_active_count,
        "exhibitor_with_booth_count": exhibitor_with_booth_count,
        "exhibitor_with_product_count": exhibitor_with_product_count,
        "procurement_total": procurement_total,
        "procurement_matched": procurement_matched,
        "procurement_match_rate": procurement_match_rate,
    })


@router.get("/stats/users/growth")
def get_user_growth(
    period: Optional[str] = Query(default="month", description="统计周期: week/month/year"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """用户增长趋势

    返回各角色的增长数据点（桩实现，返回空数组）。
    后续可按日期分组统计 users.created_at。
    """
    _require_admin_or_organizer(current_user)

    return _ok({
        "visitor_growth": [],
        "exhibitor_growth": [],
        "organizer_growth": [],
        "boss_growth": [],
        "total_growth": [],
        "period": period,
    })


@router.get("/stats/exhibitions/trend")
def get_exhibition_trend(
    period: Optional[str] = Query(default="month", description="统计周期: week/month/year"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """展会趋势

    返回展会创建、发布、报名的趋势数据（桩实现，返回空数组）。
    """
    _require_admin_or_organizer(current_user)

    return _ok({
        "exhibition_created": [],
        "exhibition_published": [],
        "registrations": [],
        "period": period,
    })


@router.get("/stats/exhibitions")
def get_exhibition_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """展会统计 — 总数、各状态分布、最近创建"""
    _require_admin_or_organizer(current_user)

    total = db.query(func.count(Exhibition.id)).scalar() or 0
    by_status = _count_by_status(db, Exhibition)

    recent = (
        db.query(Exhibition)
        .order_by(Exhibition.created_at.desc())
        .limit(10)
        .all()
    )
    recent_list = [
        {
            "id": e.id,
            "title": e.title,
            "status": e.status,
            "start_date": e.start_date,
            "end_date": e.end_date,
            "location": e.location,
            "organizer_name": e.organizer_name,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in recent
    ]

    return _ok({
        "total": total,
        "by_status": by_status,
        "recent": recent_list,
    })


@router.get("/stats/exhibitors")
def get_exhibitor_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """展商统计 — 展商数、展位数、展品数"""
    _require_admin_or_organizer(current_user)

    total_exhibitors = (
        db.query(func.count(User.id))
        .filter(User.role == "exhibitor")
        .scalar()
    ) or 0

    total_booths = db.query(func.count(Booth.id)).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0

    return _ok({
        "total_exhibitors": total_exhibitors,
        "total_booths": total_booths,
        "total_products": total_products,
    })


@router.get("/stats/procurements")
def get_procurement_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """采购统计 — 总数、各状态分布、已匹配数"""
    _require_admin_or_organizer(current_user)

    total = db.query(func.count(Procurement.id)).scalar() or 0
    by_status = _count_by_status(db, Procurement)

    matched_count = (
        db.query(func.count(Procurement.id))
        .filter(Procurement.status == "matched")
        .scalar()
    ) or 0

    return _ok({
        "total": total,
        "by_status": by_status,
        "matched_count": matched_count,
    })


# ============================================================
# 管理端点（桩实现）
# ============================================================



@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    organizer_status: str = Query(default=..., description="New status: approved or rejected"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _require_admin_or_organizer(current_user)
    
    if current_user.role != "admin":
        raise Forbidden(message="Only admin can approve users")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from app.core.exceptions import NotFound
        raise NotFound(message="User not found")

    if organizer_status not in ("approved", "rejected", "pending"):
        from app.core.exceptions import BadRequest
        raise BadRequest(message="Status must be approved, rejected, or pending")

    user.organizer_status = organizer_status
    db.commit()

    return _ok({
        "message": f"User status updated to {organizer_status}",
        "user_id": user_id,
        "organizer_status": organizer_status,
    })


@router.get("/users/pending-count")
def get_pending_users_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _require_admin_or_organizer(current_user)

    count = db.query(func.count(User.id)).filter(
        User.role.in_(["exhibitor", "organizer"]),
        User.organizer_status == "pending"
    ).scalar() or 0

    return _ok({"pending_count": count})


@router.get("/teams")
def get_team_list(current_user: User = Depends(get_current_active_user)):
    """团队列表（桩 — 待实现）"""
    _require_admin_or_organizer(current_user)
    return _ok([])


@router.post("/teams")
def create_team(current_user: User = Depends(get_current_active_user)):
    """创建团队（桩 — 待实现）"""
    _require_admin_or_organizer(current_user)
    return _ok({"id": 0, "name": "stub", "message": "待实现"})


@router.get("/users")
def get_user_list(
    role: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """用户列表（简易实现）"""
    _require_admin_or_organizer(current_user)

    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if status:
        q = q.filter(User.status == status)

    total = q.count()
    users = q.offset((page - 1) * 20).limit(20).all()

    items = [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "status": u.status,
            "organizer_status": u.organizer_status,
            "nickname": u.nickname,
            "company": u.company,
            "company_name": u.company_name,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]

    return _ok({"list": items, "total": total, "page": page})


@router.get("/approvals")
def get_approval_list(
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """审批列表（桩 — 返回待审核的主办方/展会列表）"""
    _require_admin_or_organizer(current_user)

    items = []
    # 主办方审批
    if not type or type == "organizer":
        organizers = db.query(User).filter(
            User.role == "organizer",
            User.organizer_status == "pending" if not status or status == "pending"
            else User.organizer_status == status,
        ).all()
        for o in organizers:
            items.append({
                "id": o.id,
                "type": "organizer",
                "title": o.company_name or o.username,
                "applicant_name": o.username,
                "status": o.organizer_status or "pending",
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })

    # 展会审批
    if not type or type == "exhibition":
        q = db.query(Exhibition)
        if status:
            q = q.filter(Exhibition.status == status)
        else:
            q = q.filter(Exhibition.status == "pending")
        exhibitions = q.all()
        for e in exhibitions:
            items.append({
                "id": e.id,
                "type": "exhibition",
                "title": e.title,
                "applicant_name": e.organizer_name or "unknown",
                "status": e.status,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            })

    return _ok({"list": items, "total": len(items), "page": page})


@router.get("/approvals/{approval_id}")
def get_approval_detail(
    approval_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """审批详情（桩）"""
    _require_admin_or_organizer(current_user)
    return _ok({"id": approval_id, "type": "unknown", "title": "stub"})


@router.post("/exhibitions/{exhibition_id}/approve")
def approve_exhibition(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """审批通过展会（管理员，或主办方本人）"""
    _require_admin_or_organizer(current_user)

    exhibition = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exhibition:
        from app.core.exceptions import NotFound
        raise NotFound(message="展会不存在")

    # 归属校验：主办方仅可审批自己创建的展会
    if current_user.role == "organizer" and exhibition.organizer_id != current_user.id:
        raise Forbidden(message="无权审批其他主办方的展会")

    exhibition.status = "published"
    db.commit()

    return _ok({"message": "展会已通过审批", "exhibition_id": exhibition_id})


@router.post("/exhibitions/{exhibition_id}/reject")
def reject_exhibition(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """驳回展会（管理员，或主办方本人）"""
    _require_admin_or_organizer(current_user)

    exhibition = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exhibition:
        from app.core.exceptions import NotFound
        raise NotFound(message="展会不存在")

    # 归属校验：主办方仅可驳回自己创建的展会
    if current_user.role == "organizer" and exhibition.organizer_id != current_user.id:
        raise Forbidden(message="无权驳回其他主办方的展会")

    exhibition.status = "draft"
    db.commit()

    return _ok({"message": "展会已被驳回", "exhibition_id": exhibition_id})

@router.get("/teams/{team_id}/members")
def get_team_members(
    team_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _require_admin_or_organizer(current_user)
    return {"success": True, "code": "OK", "message": "获取成功", "data": {"list": [], "total": 0}}

@router.post("/teams/{team_id}/members")
def add_team_member(
    team_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _require_admin_or_organizer(current_user)
    return {"success": True, "code": "OK", "message": "添加成功", "data": {}}

@router.delete("/teams/{team_id}/members/{user_id}")
def remove_team_member(
    team_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _require_admin_or_organizer(current_user)
    return {"success": True, "code": "OK", "message": "删除成功", "data": None}

@router.get("/exhibitions/{exhibition_id}/registrations")
def get_exhibition_registrations(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取展会报名列表（仅主办方本人或管理员可访问）"""
    _require_admin_or_organizer(current_user)

    # 归属校验：主办方只能查看自己展会的报名
    exhibition = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exhibition:
        from app.core.exceptions import NotFound
        raise NotFound(message="展会不存在")
    if current_user.role == "organizer" and exhibition.organizer_id != current_user.id:
        raise Forbidden(message="无权查看其他主办方的展会报名")

    from app.models.registration import Registration
    from app.models.user import User
    q = db.query(Registration).filter(Registration.exhibition_id == exhibition_id)
    total = q.count()
    regs = q.order_by(Registration.created_at.desc()).all()
    items = []
    for r in regs:
        u = db.query(User).filter(User.id == r.visitor_id).first()
        items.append({"id": r.id, "visitor_id": r.visitor_id, "username": u.username if u else "unknown", "ticket_code": r.ticket_code, "created_at": r.created_at.isoformat() if r.created_at else None})
    return {"success": True, "code": "OK", "message": "获取成功", "data": {"list": items, "total": total, "page": 1, "pageSize": 100, "totalPages": 1}}


# ============================================================
# V2.5: Boss看板
# ============================================================

@router.get("/boss")
def boss_dashboard(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Boss看板 — 平台核心指标一览"""
    if current_user.role not in ("admin", "organizer"):
        raise Forbidden(message="无权访问")

    from app.models.product import Product
    from app.models.booth import Booth
    from app.models.procurement import Procurement
    from app.models.procurement_match import ProcurementMatch
    from app.models.micro_booth import MicroBooth
    from app.models.membership import Membership
    from app.models.registration import Registration
    from app.models.analytics import AnalyticsEvent
    from app.models.notification import Notification

    # 用户统计
    total_users = db.query(func.count(User.id)).scalar() or 0
    exhibitors = db.query(func.count(User.id)).filter(User.role == "exhibitor").scalar() or 0
    buyers = db.query(func.count(User.id)).filter(User.role == "buyer").scalar() or 0
    visitors = db.query(func.count(User.id)).filter(User.role == "visitor").scalar() or 0

    # 内容统计
    total_exhibitions = db.query(func.count(Exhibition.id)).scalar() or 0
    total_booths = db.query(func.count(Booth.id)).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0
    total_procurements = db.query(func.count(Procurement.id)).scalar() or 0

    # 匹配统计
    total_matches = db.query(func.count(ProcurementMatch.id)).scalar() or 0
    accepted_matches = db.query(func.count(ProcurementMatch.id)).filter(ProcurementMatch.is_accepted == True).scalar() or 0
    match_rate = round(accepted_matches / total_matches * 100, 1) if total_matches > 0 else 0

    # 微展位统计
    total_micro_booths = db.query(func.count(MicroBooth.id)).scalar() or 0
    mb_views = db.query(func.coalesce(func.sum(MicroBooth.view_count), 0)).scalar() or 0
    mb_favs = db.query(func.coalesce(func.sum(MicroBooth.favorite_count), 0)).scalar() or 0

    # 积分统计
    total_points = db.query(func.coalesce(func.sum(User.total_points), 0)).scalar() or 0

    # 通知统计
    total_notifications = db.query(func.count(Notification.id)).scalar() or 0

    # 报名统计
    total_registrations = db.query(func.count(Registration.id)).filter(Registration.is_registered == True).scalar() or 0

    # 转化漏斗
    # 浏览 → 注册 → 创建微展位 → 获得匹配
    page_views = db.query(func.count(AnalyticsEvent.id)).filter(AnalyticsEvent.event_type == "page_view").scalar() or 0

    return {
        "success": True, "code": "OK",
        "data": {
            "users": {"total": total_users, "exhibitors": exhibitors, "buyers": buyers, "visitors": visitors},
            "content": {"exhibitions": total_exhibitions, "booths": total_booths, "products": total_products, "procurements": total_procurements},
            "matches": {"total": total_matches, "accepted": accepted_matches, "rate": match_rate},
            "micro_booths": {"total": total_micro_booths, "views": mb_views, "favorites": mb_favs},
            "engagement": {"points_distributed": total_points, "notifications_sent": total_notifications, "registrations": total_registrations, "page_views": page_views},
            "funnel": {
                "page_views": page_views,
                "registrations": total_registrations,
                "micro_booths_created": total_micro_booths,
                "successful_matches": accepted_matches,
            }
        }
    }
