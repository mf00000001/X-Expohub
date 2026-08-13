"""V2.8: 通用收藏系统（V3.0 落库版）

原实现为内存存储（user_favs 字典），收藏关系不落库而 favorite_count 写库，
重启后计数与实际收藏脱节。现改为 favorites 表存储，计数与关系事务内一致。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.user import User
from app.models.product import Product
from app.models.micro_booth import MicroBooth
from app.models.favorite import Favorite
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/favorites", tags=["收藏"])


class FavRequest(BaseModel):
    entity_type: str  # product / micro_booth / exhibition
    entity_id: int


def _toggle_counter(db: Session, entity_type: str, entity_id: int, delta: int) -> None:
    """事务内同步收藏计数（与收藏关系同事务提交）"""
    if entity_type == "product":
        p = db.query(Product).filter(Product.id == entity_id).first()
        if p:
            p.favorite_count = max((p.favorite_count or 0) + delta, 0)
    elif entity_type == "micro_booth":
        mb = db.query(MicroBooth).filter(MicroBooth.id == entity_id).first()
        if mb:
            mb.favorite_count = max((mb.favorite_count or 0) + delta, 0)


@router.post("/toggle")
def toggle_fav(
    data: FavRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    existing = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == uid,
            Favorite.entity_type == data.entity_type,
            Favorite.entity_id == data.entity_id,
        )
        .first()
    )

    if existing:
        db.delete(existing)
        _toggle_counter(db, data.entity_type, data.entity_id, -1)
        db.commit()
        return {"success": True, "code": "OK", "data": {"favorited": False}}

    fav = Favorite(user_id=uid, entity_type=data.entity_type, entity_id=data.entity_id)
    db.add(fav)
    _toggle_counter(db, data.entity_type, data.entity_id, +1)
    db.commit()
    return {"success": True, "code": "OK", "data": {"favorited": True}}


@router.get("/my")
def my_favs(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    favs = (
        db.query(Favorite)
        .filter(Favorite.user_id == uid)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    products = []
    micro_booths = []
    for f in favs:
        if f.entity_type == "product":
            p = db.query(Product).filter(Product.id == f.entity_id).first()
            if p:
                products.append({"id": p.id, "name": p.name, "category": p.category})
        elif f.entity_type == "micro_booth":
            mb = db.query(MicroBooth).filter(MicroBooth.id == f.entity_id).first()
            if mb:
                micro_booths.append({"id": mb.id, "name": mb.name, "industry_domain": mb.industry_domain})
    return {"success": True, "code": "OK", "data": {"products": products, "micro_booths": micro_booths}}


@router.get("/status")
def fav_status(
    entity_type: str,
    entity_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    existing = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == uid,
            Favorite.entity_type == entity_type,
            Favorite.entity_id == entity_id,
        )
        .first()
    )
    return {"success": True, "code": "OK", "data": {"favorited": existing is not None}}
