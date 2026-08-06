"""
V2.0: 微展位 API

端点：
- GET    /micro-booths              公开列表
- GET    /micro-booths/my           我的微展位
- GET    /micro-booths/{id}         微展位详情(含展品)
- POST   /micro-booths              创建(exhibitor)
- PUT    /micro-booths/{id}         编辑
- POST   /micro-booths/{id}/products       添加展品(检查会员限额)
- DELETE /micro-booths/{id}/products/{pid} 移除展品
- POST   /micro-booths/{id}/upgrade        升级会员
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.base import get_db
from app.models.user import User
from app.models.micro_booth import MicroBooth
from app.models.membership import Membership, TIER_PRODUCT_LIMITS
from app.models.product import Product
from app.api.deps import get_current_active_user
from app.core.exceptions import NotFound, Forbidden, BadRequest, Conflict

router = APIRouter(prefix="/micro-booths", tags=["微展位"])


# ============================================================
# Pydantic Schemas
# ============================================================

class MicroBoothCreate(BaseModel):
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    industry_domain: Optional[str] = None


class MicroBoothUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    industry_domain: Optional[str] = None


class AddProductRequest(BaseModel):
    product_id: int


class UpgradeRequest(BaseModel):
    tier: str  # regular / flagship


# ============================================================
# 辅助函数
# ============================================================

def _mb_to_dict(mb: MicroBooth, product_count: int = 0) -> dict:
    return {
        "id": mb.id,
        "exhibitor_id": mb.exhibitor_id,
        "name": mb.name,
        "description": mb.description,
        "logo_url": mb.logo_url,
        "industry_domain": mb.industry_domain,
        "membership_tier": mb.membership_tier,
        "product_limit": TIER_PRODUCT_LIMITS.get(mb.membership_tier, 3),
        "product_count": product_count,
        "view_count": mb.view_count,
        "search_appearances": mb.search_appearances,
        "favorite_count": mb.favorite_count,
        "status": mb.status,
        "created_at": mb.created_at.isoformat() if mb.created_at else None,
        "updated_at": mb.updated_at.isoformat() if mb.updated_at else None,
    }


def _product_to_dict(p: Product) -> dict:
    images = None
    if p.images:
        try: images = json.loads(p.images)
        except: images = []
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "category": p.category, "price": p.price, "unit": p.unit,
        "images": images, "stock": p.stock, "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _check_product_limit(db: Session, micro_booth_id: int) -> int:
    """检查当前微展位已挂展品数，返回当前数量"""
    count = db.query(func.count(Product.id)).filter(
        Product.micro_booth_id == micro_booth_id
    ).scalar() or 0
    return count


def _ensure_membership(db: Session, user_id: int) -> Membership:
    """确保展商有会员记录，没有则创建免费会员"""
    m = db.query(Membership).filter(Membership.user_id == user_id).first()
    if not m:
        m = Membership(user_id=user_id, tier="free", product_limit=3)
        db.add(m)
        db.flush()
    return m


# ============================================================
# 端点
# ============================================================

@router.get("")
def list_public(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    industry_domain: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """公开微展位列表"""
    q = db.query(MicroBooth).filter(MicroBooth.status == "active")
    if industry_domain:
        q = q.filter(MicroBooth.industry_domain == industry_domain)
    if search:
        from app.models.category import EXHIBITION_CATEGORIES, get_parent_group
        # 精确匹配
        exact = q.filter(
            MicroBooth.name.ilike(f"%{search}%") |
            MicroBooth.industry_domain.ilike(f"%{search}%") |
            MicroBooth.description.ilike(f"%{search}%")
        )
        exact_total = exact.count()
        if exact_total > 0:
            q = exact
        else:
            # 模糊匹配：找search关键词出现在哪个分类里，然后匹配同父组分类
            related_cats = []
            for cat in EXHIBITION_CATEGORIES:
                if search in cat:
                    related_cats.append(cat)
                    pg = get_parent_group(cat)
                    if pg:
                        for c in EXHIBITION_CATEGORIES:
                            if get_parent_group(c) == pg and c not in related_cats:
                                related_cats.append(c)
            if related_cats:
                q = q.filter(MicroBooth.industry_domain.in_(related_cats[:5]))
            # 兜底：按浏览量返回热门微展位，不返回空
    total = q.count()
    from sqlalchemy import case
    tier_order = case(
        (MicroBooth.membership_tier == 'flagship', 1),
        (MicroBooth.membership_tier == 'regular', 2),
        else_=3
    )
    items = q.order_by(tier_order, MicroBooth.updated_at.desc()).offset((page-1)*page_size).limit(page_size).all()

    result = []
    for mb in items:
        count = _check_product_limit(db, mb.id)
        result.append(_mb_to_dict(mb, count))

    return {
        "success": True, "code": "OK", "message": "获取成功",
        "data": {"list": result, "total": total, "page": page, "pageSize": page_size,
                 "totalPages": (total + page_size - 1)//page_size if page_size > 0 else 0},
    }


@router.get("/my")
def my_booths(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """我的微展位列表"""
    items = db.query(MicroBooth).filter(
        MicroBooth.exhibitor_id == current_user.id
    ).order_by(MicroBooth.created_at.desc()).all()

    result = []
    for mb in items:
        count = _check_product_limit(db, mb.id)
        result.append(_mb_to_dict(mb, count))

    return {"success": True, "code": "OK", "message": "获取成功", "data": result}


@router.get("/{mb_id}")
def get_detail(mb_id: int, db: Session = Depends(get_db)):
    """微展位详情(含展品列表)，按会员等级限制展品数"""
    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")

    limit = TIER_PRODUCT_LIMITS.get(mb.membership_tier, 3)
    total_products = db.query(Product).filter(
        Product.micro_booth_id == mb_id
    ).count()

    products = db.query(Product).filter(
        Product.micro_booth_id == mb_id
    ).order_by(Product.created_at.desc())
    if limit > 0:  # 0 = flagship unlimited
        products = products.limit(limit)
    products = products.all()

    return {
        "success": True, "code": "OK", "message": "获取成功",
        "data": {
            "booth": _mb_to_dict(mb, total_products),
            "products": [_product_to_dict(p) for p in products],
            "limit_info": {
                "tier": mb.membership_tier,
                "limit": limit,
                "total": total_products,
                "shown": len(products),
                "upgrade_hint": f"已展示{len(products)}/{total_products}个展品，升级会员展示全部" if limit > 0 and total_products > limit else None,
            }
        },
    }


@router.post("")
def create_booth(
    data: MicroBoothCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """创建微展位（展商）"""
    if current_user.role not in ("exhibitor", "admin"):
        raise Forbidden(message="仅展商可创建微展位")

    # 确保有会员记录
    _ensure_membership(db, current_user.id)

    mb = MicroBooth(
        exhibitor_id=current_user.id,
        name=data.name,
        description=data.description,
        logo_url=data.logo_url,
        industry_domain=data.industry_domain or current_user.industry_domain,
        membership_tier="free",
    )
    db.add(mb)
    db.commit()
    db.refresh(mb)

    return {"success": True, "code": "OK", "message": "微展位创建成功", "data": _mb_to_dict(mb, 0)}


@router.put("/{mb_id}")
def update_booth(
    mb_id: int,
    data: MicroBoothUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """编辑微展位"""
    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")
    if mb.exhibitor_id != current_user.id and current_user.role != "admin":
        raise Forbidden(message="无权编辑此微展位")

    updates = data.model_dump(exclude_unset=True)
    for k, v in updates.items():
        if hasattr(mb, k):
            setattr(mb, k, v)
    db.commit()
    db.refresh(mb)

    count = _check_product_limit(db, mb.id)
    return {"success": True, "code": "OK", "message": "更新成功", "data": _mb_to_dict(mb, count)}


@router.post("/{mb_id}/products")
def add_product(
    mb_id: int,
    data: AddProductRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """向微展位添加展品（检查会员限额）"""
    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")
    if mb.exhibitor_id != current_user.id:
        raise Forbidden(message="无权操作此微展位")

    # 检查限额
    limit = TIER_PRODUCT_LIMITS.get(mb.membership_tier, 3)
    current_count = _check_product_limit(db, mb.id)
    if limit > 0 and current_count >= limit:
        raise BadRequest(
            message=f"当前{mb.membership_tier}会员最多可挂{limit}个展品，已用{current_count}个。请升级会员以添加更多展品"
        )

    # 检查展品是否属于当前用户
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise NotFound(message="展品不存在")
    if product.exhibitor_id != current_user.id:
        raise Forbidden(message="无权操作此展品")

    product.micro_booth_id = mb_id
    db.commit()

    count = _check_product_limit(db, mb.id)
    return {"success": True, "code": "OK", "message": "展品已添加到微展位", "data": _mb_to_dict(mb, count)}


@router.delete("/{mb_id}/products/{product_id}")
def remove_product(
    mb_id: int, product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """从微展位移除展品"""
    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")
    if mb.exhibitor_id != current_user.id:
        raise Forbidden(message="无权操作此微展位")

    product = db.query(Product).filter(
        Product.id == product_id, Product.micro_booth_id == mb_id
    ).first()
    if not product:
        raise NotFound(message="该展品未挂在此微展位")

    product.micro_booth_id = None
    db.commit()
    return {"success": True, "code": "OK", "message": "展品已移除", "data": None}


@router.post("/{mb_id}/upgrade")
def upgrade_membership(
    mb_id: int,
    data: UpgradeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """升级会员等级"""
    if data.tier not in ("regular", "flagship"):
        raise BadRequest(message="无效的会员等级，可选: regular, flagship")

    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")
    if mb.exhibitor_id != current_user.id:
        raise Forbidden(message="无权操作")

    old_tier = mb.membership_tier
    mb.membership_tier = data.tier

    # 更新会员记录
    membership = _ensure_membership(db, current_user.id)
    membership.tier = data.tier
    membership.product_limit = TIER_PRODUCT_LIMITS[data.tier]

    db.commit()
    db.refresh(mb)

    count = _check_product_limit(db, mb.id)
    return {
        "success": True, "code": "OK",
        "message": f"已从 {old_tier} 升级为 {data.tier}",
        "data": _mb_to_dict(mb, count),
    }
