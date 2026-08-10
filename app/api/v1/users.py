"""用户 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_auth, require_boss
from app.database.session import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.user import UserProfileUpdate, UserResponse, UserSimpleResponse
from app.services import user_service

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_my_profile(current_user=Depends(require_auth)):
    """获取当前用户个人信息"""
    user = current_user.user
    return ApiResponse(data=UserResponse.model_validate(user))


@router.put("/me", response_model=ApiResponse[UserResponse])
async def update_my_profile(
    data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """更新当前用户个人信息"""
    user = user_service.update_user_profile(db, current_user.id, data)
    return ApiResponse(data=UserResponse.model_validate(user))


@router.get("/{user_id}", response_model=ApiResponse[UserSimpleResponse])
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """获取指定用户的公开信息"""
    user = user_service.get_user_by_id(db, user_id)
    return ApiResponse(data=UserSimpleResponse(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        role=user.role,
        company=user.company,
    ))


@router.get("/", response_model=ApiResponse[PaginatedResponse[UserResponse]])
async def list_users(
    page: int = 1,
    page_size: int = 20,
    role: str = None,
    status: str = None,
    keyword: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """获取用户列表（仅老板可查看）"""
    users, total = user_service.get_user_list(
        db, page=page, page_size=page_size,
        role=role, status=status, keyword=keyword,
    )
    total_pages = (total + page_size - 1) // page_size
    return ApiResponse(data=PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ))
