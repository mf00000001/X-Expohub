"""
评价路由（Reviews）

端点：
- GET    /reviews      评价列表
- POST   /reviews      创建评价
- PUT    /reviews/:id  更新评价
- DELETE /reviews/:id  删除评价
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.exceptions import NotFound, Forbidden, BadRequest
from app.models.base import get_db
from app.models.user import User
from app.models.review import Review
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/reviews", tags=["评价"])


# ============================================================
# Pydantic Schemas
# ============================================================

class ReviewCreate(BaseModel):
    """创建评价请求"""
    target_type: str = Field(..., description="评价目标类型：exhibition/booth/product")
    target_id: int = Field(..., description="评价目标 ID")
    rating: int = Field(..., ge=1, le=5, description="评分（1-5 星）")
    content: str = Field(..., min_length=1, description="评价内容")


class ReviewUpdate(BaseModel):
    """更新评价请求（所有字段可选）"""
    rating: Optional[int] = Field(default=None, ge=1, le=5, description="评分（1-5 星）")
    content: Optional[str] = Field(default=None, min_length=1, description="评价内容")


# ============================================================
# 辅助函数
# ============================================================

def _review_to_dict(review: Review) -> dict:
    """将 Review 模型转为前端响应格式"""
    return {
        "id": review.id,
        "exhibition_id": review.exhibition_id,
        "booth_id": review.booth_id,
        "reviewer_id": review.reviewer_id,
        "reviewer_name": review.reviewer_name,
        "target_type": review.target_type,
        "target_id": review.target_id,
        "rating": review.rating,
        "content": review.content,
        "created_at": review.created_at,
    }


def _paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    """构建分页响应 data"""
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
    target_type: Optional[str] = Query(default=None, description="评价目标类型"),
    target_id: Optional[int] = Query(default=None, description="评价目标 ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取评价列表

    - 同时提供 target_type 和 target_id：返回针对该目标的所有评价（不分页）
    - 仅提供 target_type：分页返回该类型的所有评价
    - 均不提供：分页返回全部评价
    """
    q = db.query(Review)

    if target_type:
        q = q.filter(Review.target_type == target_type)

    if target_id is not None:
        q = q.filter(Review.target_id == target_id)

    # 同时提供 target_type 和 target_id → 不分页，直接返回数组
    if target_type and target_id is not None:
        reviews = q.order_by(Review.created_at.desc()).all()
        return {
            "success": True,
            "code": "OK",
            "message": "获取成功",
            "data": [_review_to_dict(r) for r in reviews],
        }

    # 分页
    total = q.count()
    reviews = q.order_by(Review.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_review_to_dict(r) for r in reviews], total, page, page_size
        ),
    }


@router.post("")
def create(
    data: ReviewCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """创建评价（需登录）"""
    # 验证 target_type
    if data.target_type not in ("exhibition", "booth", "product"):
        raise BadRequest(message="评价目标类型无效，可选值：exhibition/booth/product")

    review = Review(
        reviewer_id=current_user.id,
        reviewer_name=current_user.nickname or current_user.username,
        target_type=data.target_type,
        target_id=data.target_id,
        rating=data.rating,
        content=data.content,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return {
        "success": True,
        "code": "OK",
        "message": "评价创建成功",
        "data": _review_to_dict(review),
    }


@router.put("/{review_id}")
def update(
    review_id: int,
    data: ReviewUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """更新评价（仅创建者本人）"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise NotFound(message="评价不存在")

    if review.reviewer_id != current_user.id:
        raise Forbidden(message="只能编辑自己的评价")

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise BadRequest(message="没有提供需要更新的字段")

    for field, value in updates.items():
        if hasattr(review, field):
            setattr(review, field, value)

    db.commit()
    db.refresh(review)

    return {
        "success": True,
        "code": "OK",
        "message": "评价更新成功",
        "data": _review_to_dict(review),
    }


@router.delete("/{review_id}")
def delete(
    review_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """删除评价（创建者本人或管理员）"""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise NotFound(message="评价不存在")

    # 仅创建者或管理员可删除
    is_owner = review.reviewer_id == current_user.id
    is_admin = current_user.role in ("organizer", "admin")
    if not is_owner and not is_admin:
        raise Forbidden(message="无权删除此评价")

    db.delete(review)
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "评价已删除",
        "data": None,
    }
