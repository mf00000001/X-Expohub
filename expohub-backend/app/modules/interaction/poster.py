"""
V2.3: 一键生成展商名片海报
返回展商所有展示数据，前端渲染成海报
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.base import get_db
from app.models.user import User
from app.models.product import Product
from app.models.booth import Booth
from app.models.micro_booth import MicroBooth
from app.models.analytics import AnalyticsEvent
from app.models.procurement_match import ProcurementMatch
from app.core.deps import get_current_active_user
from app.core.exceptions import NotFound, Forbidden

router = APIRouter(prefix="/poster", tags=["海报"])


@router.get("/exhibitor")
def get_poster_data(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取展商海报数据（JSON），前端渲染图片"""
    if current_user.role not in ("exhibitor", "admin"):
        raise Forbidden(message="仅展商可使用此功能")

    uid = current_user.id

    # 基础信息
    company_name = current_user.company or current_user.nickname or current_user.username
    domain = current_user.industry_domain or "综合"

    # 展品 Top 4
    products = db.query(Product).filter(
        Product.exhibitor_id == uid, Product.status == "published"
    ).order_by(Product.created_at.desc()).limit(4).all()

    product_list = []
    for p in products:
        imgs = []
        if p.images:
            try: imgs = json.loads(p.images)[:2]
            except: pass
        product_list.append({
            "name": p.name, "price": p.price, "images": imgs,
        })

    # 统计数据
    view_count = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == uid,
        AnalyticsEvent.event_type == "page_view",
    ).scalar() or 0

    fav_count = db.query(func.count(AnalyticsEvent.id)).filter(
        AnalyticsEvent.source_user_id == uid,
        AnalyticsEvent.event_type == "favorite",
    ).scalar() or 0

    match_count = db.query(func.count(ProcurementMatch.id)).filter(
        ProcurementMatch.exhibitor_id == uid,
        ProcurementMatch.is_accepted == True,
    ).scalar() or 0

    # 微展位
    mb = db.query(MicroBooth).filter(
        MicroBooth.exhibitor_id == uid, MicroBooth.status == "active"
    ).first()
    mb_views = mb.view_count if mb else 0
    mb_favs = mb.favorite_count if mb else 0

    return {
        "success": True, "code": "OK",
        "data": {
            "company_name": company_name,
            "industry_domain": domain,
            "position": current_user.position or "",
            "bio": current_user.bio or "",
            "logo": current_user.avatar_url or "",
            "exhibitor_tier": current_user.exhibitor_tier or "bronze",
            "referral_code": current_user.referral_code or "",
            "stats": {
                "views": view_count + mb_views,
                "favorites": fav_count + mb_favs,
                "matches": match_count,
                "products": len(product_list),
            },
            "products": product_list,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
