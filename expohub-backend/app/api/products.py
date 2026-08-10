"""
展品路由（Products）

端点：
- GET    /products          展品列表（分页 + 筛选）
- GET    /products/my       我的展品（展商）
- GET    /products/{id}     展品详情
- POST   /products          创建展品
- PUT    /products/{id}     更新展品
- DELETE /products/{id}     删除展品
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.exceptions import NotFound, Forbidden, BadRequest
from app.models.base import get_db
from app.models.user import User
from app.models.product import Product
from app.models.booth import Booth
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/products", tags=["展品"])


# ============================================================
# Pydantic Schemas
# ============================================================

class ProductCreate(BaseModel):
    """创建展品请求"""
    name: str
    booth_id: Optional[int] = None
    exhibition_id: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    images: Optional[list[str]] = None
    video_url: Optional[str] = None
    specs: Optional[dict] = None
    status: Optional[str] = "draft"


class ProductUpdate(BaseModel):
    """更新展品请求（所有字段可选）"""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    images: Optional[list[str]] = None
    video_url: Optional[str] = None
    specs: Optional[dict] = None
    status: Optional[str] = None


# ============================================================
# 辅助函数
# ============================================================

def _product_to_dict(product: Product) -> dict:
    """将 Product 模型转为前端响应格式（匹配 ProductItem 接口）"""
    # 解析 images JSON 字符串为列表
    images = None
    if product.images:
        try:
            images = json.loads(product.images)
        except (json.JSONDecodeError, TypeError):
            images = []

    # 解析 specs JSON 字符串为字典
    specs = None
    if product.specs:
        try:
            specs = json.loads(product.specs)
        except (json.JSONDecodeError, TypeError):
            specs = {}

    return {
        "id": product.id,
        "exhibitor_id": product.exhibitor_id,
        "exhibitor_username": product.exhibitor_name,
        "booth_id": product.booth_id,
        "exhibition_id": product.exhibition_id,
        "name": product.name,
        "name_en": product.name_en,
        "description": product.description,
        "description_en": product.description_en,
        "category": product.category,
        "images": images,
        "video_url": product.video_url,
        "price": None,  # 公开API不透露价格
        "view_count": product.view_count or 0,
        "favorite_count": product.favorite_count or 0,
        "search_appearances": product.search_appearances or 0,
        # V2.3: 广交会风格交易信息
        "model_number": product.model_number,
        "material": product.material,
        "min_order": product.min_order,
        "supply_ability": product.supply_ability,
        "delivery_time": product.delivery_time,
        "certifications": product.certifications,
        "target_market": product.target_market,
        "specs": specs,
        "status": product.status,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


def _paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    """构建分页响应数据"""
    return {
        "list": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }


# ============================================================
# 端点
# ============================================================

@router.get("")
def get_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    booth_id: Optional[int] = Query(default=None),
    exhibition_id: Optional[int] = Query(default=None),
    exhibitor_id: Optional[int] = Query(default=None),
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """获取展品列表（分页 + 多条件筛选）

    - exhibition_id: 支持直接字段或 JOIN booth 表筛选
    - search: 模糊匹配 name 和 description
    """
    q = db.query(Product)

    # 按 booth_id 筛选
    if booth_id is not None:
        q = q.filter(Product.booth_id == booth_id)

    # 按 exhibition_id 筛选（直接字段或 JOIN booth 表）
    if exhibition_id is not None:
        q = q.outerjoin(Booth, Product.booth_id == Booth.id).filter(
            or_(
                Product.exhibition_id == exhibition_id,
                Booth.exhibition_id == exhibition_id,
            )
        )

    # 按 exhibitor_id 筛选
    if exhibitor_id is not None:
        q = q.filter(Product.exhibitor_id == exhibitor_id)

    # 按 category 筛选
    if category:
        q = q.filter(Product.category == category)

    # 按 status 筛选
    if status:
        q = q.filter(Product.status == status)

    # 模糊搜索 name 和 description
    if search:
        like_pattern = f"%{search}%"
        q = q.filter(
            or_(
                Product.name.like(like_pattern),
                Product.description.like(like_pattern),
            )
        )

    # Filter: only show products from approved exhibitors (unless filtering by own ID)
    if exhibitor_id is None:
        q = q.join(User, Product.exhibitor_id == User.id).filter(
            (User.role != "exhibitor") | (User.organizer_status == None) | (User.organizer_status == "approved")
        )
    
    total = q.count()
    products = q.order_by(Product.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_product_to_dict(p) for p in products], total, page, page_size
        ),
    }


@router.get("/my")
def get_my_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("exhibitor", "admin"):
        return {"success": True, "code": "OK", "message": "非展商用户无展品", "data": {"list": [], "total": 0, "page": 1, "pageSize": 20, "totalPages": 0}}
    return _orig_get_my_products(page, page_size, current_user, db)

def _orig_get_my_products(
    page: int, page_size: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取当前用户（展商）的展品列表"""
    q = db.query(Product).filter(Product.exhibitor_id == current_user.id)

    total = q.count()
    products = q.order_by(Product.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_product_to_dict(p) for p in products], total, page, page_size
        ),
    }


@router.get("/{product_id}")
def get_by_id(
    product_id: int,
    db: Session = Depends(get_db),
):
    """获取展品详情"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise NotFound(message="展品不存在")

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _product_to_dict(product),
    }


@router.post("")
def create(
    data: ProductCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """创建展品（仅展商 exhibitor）

    自动设置 exhibitor_id 和 exhibitor_name 为当前用户信息。
    """
    if current_user.role != "exhibitor":
        raise Forbidden(message="仅展商可创建展品")

    # 如果指定了 booth_id，检查展位是否存在
    if data.booth_id is not None:
        booth = db.query(Booth).filter(Booth.id == data.booth_id).first()
        if not booth:
            raise NotFound(message="展位不存在")

    # 序列化 images 列表为 JSON 字符串
    images_str = None
    if data.images is not None:
        images_str = json.dumps(data.images, ensure_ascii=False)

    # 序列化 specs 字典为 JSON 字符串
    specs_str = None
    if data.specs is not None:
        specs_str = json.dumps(data.specs, ensure_ascii=False)

    product = Product(
        booth_id=data.booth_id,
        exhibition_id=data.exhibition_id,
        exhibitor_id=current_user.id,
        exhibitor_name=current_user.nickname or current_user.username,
        name=data.name,
        description=data.description,
        category=data.category,
        price=data.price,
        images=images_str,
        video_url=data.video_url,
        specs=specs_str,
        status=data.status or "draft",
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    return {
        "success": True,
        "code": "OK",
        "message": "展品创建成功",
        "data": _product_to_dict(product),
    }


@router.put("/{product_id}")
def update(
    product_id: int,
    data: ProductUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """更新展品（仅创建者或管理员）"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise NotFound(message="展品不存在")

    # 权限：创建者 或 管理员
    is_owner = product.exhibitor_id == current_user.id
    is_admin = current_user.role in ("organizer", "admin")
    if not is_owner and not is_admin:
        raise Forbidden(message="无权编辑此展品")

    updates = data.model_dump(exclude_unset=True)

    # images 需要特殊处理：list[str] -> JSON 字符串
    if "images" in updates and updates["images"] is not None:
        updates["images"] = json.dumps(updates["images"], ensure_ascii=False)

    # specs 需要特殊处理：dict -> JSON 字符串
    if "specs" in updates and updates["specs"] is not None:
        updates["specs"] = json.dumps(updates["specs"], ensure_ascii=False)

    for field, value in updates.items():
        if hasattr(product, field):
            setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return {
        "success": True,
        "code": "OK",
        "message": "展品更新成功",
        "data": _product_to_dict(product),
    }


@router.delete("/{product_id}")
def delete(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """删除展品（仅创建者或管理员）"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise NotFound(message="展品不存在")

    # 权限：创建者 或 管理员
    is_owner = product.exhibitor_id == current_user.id
    is_admin = current_user.role in ("organizer", "admin")
    if not is_owner and not is_admin:
        raise Forbidden(message="无权删除此展品")

    db.delete(product)
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "展品已删除",
        "data": None,
    }
