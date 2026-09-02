"""
Exhibitor Profile Routes

端点：
- GET /exhibitors/{id}/profile  展商公开主页数据
- PUT /exhibitors/domain        展商更新行业领域 (V2.0)
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.exceptions import NotFound, Forbidden
from app.models.base import get_db
from app.models.user import User
from app.models.booth import Booth
from app.models.product import Product
from app.models.procurement_match import ProcurementMatch
from app.core.deps import get_current_active_user

router = APIRouter(prefix="/exhibitors", tags=["展商"])


class DomainUpdateRequest(BaseModel):
    """V2.0: 展商行业领域更新"""
    industry_domain: str  # 主行业领域
    sub_domains: Optional[list[str]] = None  # 细分领域


def _product_to_dict(product: Product) -> dict:
    import json
    images = None
    if product.images:
        try:
            images = json.loads(product.images)
        except (json.JSONDecodeError, TypeError):
            images = []
    specs = None
    if product.specs:
        try:
            specs = json.loads(product.specs)
        except (json.JSONDecodeError, TypeError):
            specs = {}
    return {
        "id": product.id,
        "name": product.name,
        "name_en": product.name_en,
        "description": product.description,
        "description_en": product.description_en,
        "category": product.category,
        "price": product.price,
        "images": images,
        "specs": specs,
        "status": product.status,
        "booth_id": product.booth_id,
        "exhibition_id": product.exhibition_id,
        "created_at": product.created_at.isoformat() if product.created_at else None,
    }


def _booth_to_dict(booth: Booth) -> dict:
    return {
        "id": booth.id,
        "exhibition_id": booth.exhibition_id,
        "booth_number": booth.booth_number,
        "size": booth.size,
        "location_area": booth.location_area,
        "price": booth.price,
        "status": booth.status,
        "description": booth.description,
        "created_at": booth.created_at.isoformat() if booth.created_at else None,
    }


@router.get("/{exhibitor_id}/profile")
def get_exhibitor_profile(
    exhibitor_id: int,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == exhibitor_id).first()
    if not user:
        raise NotFound(message="展商不存在")

    booths = db.query(Booth).filter(
        Booth.exhibitor_id == exhibitor_id
    ).order_by(Booth.created_at.desc()).all()

    products = db.query(Product).filter(
        Product.exhibitor_id == exhibitor_id
    ).order_by(Product.created_at.desc()).all()

    match_count = db.query(func.count(ProcurementMatch.id)).filter(
        ProcurementMatch.exhibitor_id == exhibitor_id
    ).scalar() or 0

    # V2.0: 解析行业领域
    sub_domains_list = None
    if user.sub_domains:
        try:
            sub_domains_list = json.loads(user.sub_domains)
        except (json.JSONDecodeError, TypeError):
            sub_domains_list = []

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": {
            "company": {
                "id": user.id,
                "username": user.username,
                "company": user.company,
                "company_name": user.company_name,
                "position": user.position,
                "bio": user.bio,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "role": user.role,
                "organizer_status": user.organizer_status,
                # V2.0
                "industry_domain": user.industry_domain,
                "sub_domains": sub_domains_list,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "booths": [_booth_to_dict(b) for b in booths],
            "products": [_product_to_dict(p) for p in products],
            "stats": {
                "total_products": len(products),
                "total_booths": len(booths),
                "match_count": match_count,
            },
        },
    }


# ============================================================
# V2.0: 展商行业领域
# ============================================================

@router.put("/domain")
def update_domain(
    data: DomainUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """展商更新所属行业领域

    前端调用：PUT /exhibitors/domain
    请求体：{"industry_domain": "电子及家电", "sub_domains": ["消费电子", "智能家居"]}
    """
    if current_user.role not in ("exhibitor", "admin", "organizer"):
        raise Forbidden(message="仅展商可设置行业领域")

    current_user.industry_domain = data.industry_domain
    if data.sub_domains:
        current_user.sub_domains = json.dumps(data.sub_domains, ensure_ascii=False)
    db.commit()
    db.refresh(current_user)

    sub_list = None
    if current_user.sub_domains:
        try:
            sub_list = json.loads(current_user.sub_domains)
        except (json.JSONDecodeError, TypeError):
            sub_list = []

    return {
        "success": True,
        "code": "OK",
        "message": "行业领域更新成功",
        "data": {
            "industry_domain": current_user.industry_domain,
            "sub_domains": sub_list,
        },
    }
