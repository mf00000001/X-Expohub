"""V2.8: 通用收藏系统"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.user import User
from app.models.product import Product
from app.models.micro_booth import MicroBooth
from app.api.deps import get_current_active_user
from app.core.exceptions import NotFound

router = APIRouter(prefix="/favorites", tags=["收藏"])

# 内存存储（简单方案，不建新表）
user_favs = {}  # {user_id: [(entity_type, entity_id), ...]}

class FavRequest(BaseModel):
    entity_type: str  # product / micro_booth / exhibition
    entity_id: int

@router.post("/toggle")
def toggle_fav(data: FavRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    uid = current_user.id
    key = (data.entity_type, data.entity_id)
    if uid not in user_favs: user_favs[uid] = []
    favs = user_favs[uid]
    if key in favs:
        favs.remove(key)
        # Decrement counter
        if data.entity_type == "product":
            p = db.query(Product).filter(Product.id == data.entity_id).first()
            if p and p.favorite_count > 0: p.favorite_count -= 1; db.commit()
        elif data.entity_type == "micro_booth":
            mb = db.query(MicroBooth).filter(MicroBooth.id == data.entity_id).first()
            if mb and mb.favorite_count > 0: mb.favorite_count -= 1; db.commit()
        return {"success": True, "code": "OK", "data": {"favorited": False}}
    else:
        favs.append(key)
        if data.entity_type == "product":
            p = db.query(Product).filter(Product.id == data.entity_id).first()
            if p: p.favorite_count = (p.favorite_count or 0) + 1; db.commit()
        elif data.entity_type == "micro_booth":
            mb = db.query(MicroBooth).filter(MicroBooth.id == data.entity_id).first()
            if mb: mb.favorite_count = (mb.favorite_count or 0) + 1; db.commit()
        return {"success": True, "code": "OK", "data": {"favorited": True}}

@router.get("/my")
def my_favs(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    uid = current_user.id
    favs = user_favs.get(uid, [])
    products = []; micro_booths = []
    for et, eid in favs:
        if et == "product":
            p = db.query(Product).filter(Product.id == eid).first()
            if p: products.append({"id": p.id, "name": p.name, "category": p.category})
        elif et == "micro_booth":
            mb = db.query(MicroBooth).filter(MicroBooth.id == eid).first()
            if mb: micro_booths.append({"id": mb.id, "name": mb.name, "industry_domain": mb.industry_domain})
    return {"success": True, "code": "OK", "data": {"products": products, "micro_booths": micro_booths}}

@router.get("/status")
def fav_status(entity_type: str, entity_id: int, current_user: User = Depends(get_current_active_user)):
    uid = current_user.id
    favs = user_favs.get(uid, [])
    return {"success": True, "code": "OK", "data": {"favorited": (entity_type, entity_id) in favs}}
