"""展馆路由（Venues）

- GET    /venues          展馆列表(公开,支持 city 筛选/关键词搜索)
- GET    /venues/:id      展馆详情(公开)
- POST   /venues          创建展馆(仅 admin)
- PUT    /venues/:id      更新展馆(仅 admin)
- DELETE /venues/:id      删除展馆(仅 admin)

展馆为公开数据(游客/买家/展商/主办方均可查看),写操作仅平台管理员。
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.exceptions import NotFound, Forbidden
from app.core.permissions import Permission
from app.models.base import get_db
from app.models.user import User
from app.models.venue import Venue
from app.api.deps import get_current_active_user, require_permission

router = APIRouter(prefix="/venues", tags=["展馆"])


class VenueCreate(BaseModel):
    name: str
    city: str
    address: str
    area: Optional[float] = None
    important_info: Optional[str] = None
    honors: Optional[list[str]] = None
    plan_image: Optional[str] = None  # 场馆平面图(URL 或 data URI)


class VenueUpdate(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    area: Optional[float] = None
    important_info: Optional[str] = None
    honors: Optional[list[str]] = None
    plan_image: Optional[str] = None


def _venue_to_dict(v: Venue) -> dict:
    honors = []
    if v.honors:
        try:
            honors = json.loads(v.honors) if isinstance(v.honors, str) else list(v.honors)
        except (ValueError, TypeError):
            honors = []
    return {
        "id": v.id,
        "name": v.name,
        "city": v.city,
        "address": v.address,
        "area": v.area,
        "important_info": v.important_info or "",
        "honors": honors,
        "plan_image": v.plan_image or "",
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.get("")
def get_list(
    city: Optional[str] = Query(default=None, description="按城市筛选"),
    q: Optional[str] = Query(default=None, description="关键词(名称/地址)"),
    db: Session = Depends(get_db),
):
    """展馆列表(公开)"""
    qq = db.query(Venue)
    if city:
        qq = qq.filter(Venue.city == city)
    if q:
        qq = qq.filter(or_(Venue.name.contains(q), Venue.address.contains(q)))
    venues = qq.order_by(Venue.city, Venue.name).all()
    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": {"list": [_venue_to_dict(v) for v in venues], "total": len(venues)},
    }


@router.get("/{venue_id}")
def get_detail(venue_id: int, db: Session = Depends(get_db)):
    """展馆详情(公开)"""
    v = db.query(Venue).filter(Venue.id == venue_id).first()
    if not v:
        raise NotFound(message="展馆不存在")
    return {"success": True, "code": "OK", "message": "获取成功", "data": _venue_to_dict(v)}


@router.post("")
def create(
    data: VenueCreate,
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
    db: Session = Depends(get_db),
):
    """创建展馆(仅 admin)"""
    v = Venue(
        name=data.name,
        city=data.city,
        address=data.address,
        area=data.area,
        important_info=data.important_info,
        honors=json.dumps(data.honors, ensure_ascii=False) if data.honors else None,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return {"success": True, "code": "OK", "message": "展馆创建成功", "data": _venue_to_dict(v)}


@router.put("/{venue_id}")
def update(
    venue_id: int,
    data: VenueUpdate,
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
    db: Session = Depends(get_db),
):
    """更新展馆(仅 admin)"""
    v = db.query(Venue).filter(Venue.id == venue_id).first()
    if not v:
        raise NotFound(message="展馆不存在")
    updates = data.model_dump(exclude_unset=True)
    if "honors" in updates and updates["honors"] is not None:
        updates["honors"] = json.dumps(updates["honors"], ensure_ascii=False)
    for field, value in updates.items():
        if hasattr(v, field):
            setattr(v, field, value)
    db.commit()
    db.refresh(v)
    return {"success": True, "code": "OK", "message": "展馆更新成功", "data": _venue_to_dict(v)}


@router.delete("/{venue_id}")
def delete(
    venue_id: int,
    current_user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
    db: Session = Depends(get_db),
):
    """删除展馆(仅 admin)"""
    v = db.query(Venue).filter(Venue.id == venue_id).first()
    if not v:
        raise NotFound(message="展馆不存在")
    db.delete(v)
    db.commit()
    return {"success": True, "code": "OK", "message": "展馆已删除", "data": None}
