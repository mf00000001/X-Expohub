"""
V2.2: 埋点上报 API
前端自动调用，对用户透明
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.analytics import AnalyticsEvent

router = APIRouter(prefix="/analytics", tags=["埋点"])


class TrackEventRequest(BaseModel):
    event_type: str      # page_view / search_impression / favorite / booking / inquiry
    entity_type: str     # exhibition / booth / product / micro_booth
    entity_id: int
    source_user_id: Optional[int] = None  # 被浏览的展商
    metadata: Optional[str] = None        # JSON 附加信息


@router.post("/event")
def track_event(data: TrackEventRequest, db: Session = Depends(get_db)):
    """上报用户行为事件（无需登录）"""
    event = AnalyticsEvent(
        event_type=data.event_type,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        source_user_id=data.source_user_id,
        extra_data=data.metadata,
    )
    db.add(event)

    # 一人一天只算一次浏览（去重）
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    already = db.query(AnalyticsEvent).filter(
        AnalyticsEvent.event_type == data.event_type,
        AnalyticsEvent.entity_type == data.entity_type,
        AnalyticsEvent.entity_id == data.entity_id,
        AnalyticsEvent.user_id == event.user_id,
        AnalyticsEvent.created_at >= today,
    ).count()
    if already > 1:
        db.commit()
        return {"success": True, "code": "OK", "message": "dedup"}

    # 同步更新微展位/展品计数
    if data.event_type in ("page_view", "search_impression", "favorite"):
        if data.entity_type == "micro_booth":
            from app.models.micro_booth import MicroBooth
            mb = db.query(MicroBooth).filter(MicroBooth.id == data.entity_id).first()
            if mb:
                if data.event_type == "page_view": mb.view_count = (mb.view_count or 0) + 1
                elif data.event_type == "search_impression": mb.search_appearances = (mb.search_appearances or 0) + 1
                elif data.event_type == "favorite": mb.favorite_count = (mb.favorite_count or 0) + 1
        elif data.entity_type == "product":
            from app.models.product import Product
            p = db.query(Product).filter(Product.id == data.entity_id).first()
            if p:
                if data.event_type == "page_view": p.view_count = (p.view_count or 0) + 1
                elif data.event_type == "search_impression": p.search_appearances = (p.search_appearances or 0) + 1
                elif data.event_type == "favorite": p.favorite_count = (p.favorite_count or 0) + 1

    db.commit()
    # V2.3: 浏览自动加积分
    if data.source_user_id and data.event_type in ("page_view", "favorite"):
        try:
            from app.modules.identity.points import earn_points
            earn_points(data.source_user_id, f"earn_{data.event_type}", data.entity_type, data.entity_id, db)
        except: pass
    return {"success": True, "code": "OK", "message": "ok"}
