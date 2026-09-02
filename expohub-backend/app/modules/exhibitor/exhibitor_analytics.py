"""
V2.2: 展商数据看板 API
全部从真实数据聚合，不是死数字
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.base import get_db
from app.models.user import User
from app.models.analytics import AnalyticsEvent
from app.models.micro_booth import MicroBooth
from app.models.product import Product
from app.models.booth import Booth
from app.models.procurement_match import ProcurementMatch
from app.core.deps import get_current_active_user
from app.core.exceptions import Forbidden

router = APIRouter(prefix="/exhibitor/analytics", tags=["展商看板"])


def _today_start():
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/overview")
def overview(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """展商数据总览：今日 & 总计"""
    if current_user.role not in ("exhibitor", "admin", "organizer"):
        raise Forbidden(message="无权访问")

    uid = current_user.id
    today = _today_start()

    # 今日数据
    today_views = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == uid,
        AnalyticsEvent.event_type == "page_view",
        AnalyticsEvent.created_at >= today,
    ).scalar() or 0

    today_searches = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == uid,
        AnalyticsEvent.event_type == "search_impression",
        AnalyticsEvent.created_at >= today,
    ).scalar() or 0

    today_favorites = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == uid,
        AnalyticsEvent.event_type == "favorite",
        AnalyticsEvent.created_at >= today,
    ).scalar() or 0

    # 总计数据
    total_views = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == uid,
        AnalyticsEvent.event_type == "page_view",
    ).scalar() or 0

    total_searches = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == uid,
        AnalyticsEvent.event_type == "search_impression",
    ).scalar() or 0

    total_favorites = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == uid,
        AnalyticsEvent.event_type == "favorite",
    ).scalar() or 0

    # 微展位汇总
    mb_total = db.query(
        func.coalesce(func.sum(MicroBooth.view_count), 0),
        func.coalesce(func.sum(MicroBooth.favorite_count), 0),
    ).filter(MicroBooth.exhibitor_id == uid).first()
    mb_views, mb_favorites = mb_total if mb_total else (0, 0)

    # 展品数
    product_count = db.query(func.count(Product.id)).filter(
        Product.exhibitor_id == uid
    ).scalar() or 0

    # 展位数
    booth_count = db.query(func.count(Booth.id)).filter(
        Booth.exhibitor_id == uid
    ).scalar() or 0

    # 采购匹配
    match_total = db.query(func.count(ProcurementMatch.id)).filter(
        ProcurementMatch.exhibitor_id == uid
    ).scalar() or 0
    match_accepted = db.query(func.count(ProcurementMatch.id)).filter(
        ProcurementMatch.exhibitor_id == uid,
        ProcurementMatch.is_accepted == True,
    ).scalar() or 0

    return {
        "success": True, "code": "OK", "data": {
            "today": {"views": today_views, "searches": today_searches, "favorites": today_favorites},
            "total": {"views": total_views + mb_views, "searches": total_searches, "favorites": total_favorites + mb_favorites},
            "products": product_count,
            "booths": booth_count,
            "matches": {"total": match_total, "accepted": match_accepted},
        }
    }


@router.get("/trend")
def trend(
    days: int = Query(default=7, ge=1, le=30),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """浏览量趋势（按天）"""
    if current_user.role not in ("exhibitor", "admin", "organizer"):
        raise Forbidden(message="无权访问")

    uid = current_user.id
    result = []
    now = datetime.now(timezone.utc)
    for i in range(days - 1, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = db.query(func.count(AnalyticsEvent.id)).filter(
            AnalyticsEvent.source_user_id == uid,
            AnalyticsEvent.event_type == "page_view",
            AnalyticsEvent.created_at >= day_start,
            AnalyticsEvent.created_at < day_end,
        ).scalar() or 0
        result.append({"date": day_start.strftime("%m-%d"), "views": count})

    return {"success": True, "code": "OK", "data": result}


@router.get("/top-products")
def top_products(
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """展商热门展品 Top N（按浏览量排序，暂用展品创建时间排序作为代理）"""
    if current_user.role not in ("exhibitor", "admin", "organizer"):
        raise Forbidden(message="无权访问")

    products = db.query(Product).filter(
        Product.exhibitor_id == current_user.id
    ).order_by(Product.created_at.desc()).limit(limit).all()

    items = []
    for p in products:
        items.append({
            "id": p.id, "name": p.name, "price": p.price, "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })

    return {"success": True, "code": "OK", "data": items}
