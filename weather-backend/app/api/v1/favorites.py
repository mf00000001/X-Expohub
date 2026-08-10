"""天气查询平台 - 收藏 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.services.favorite_service import favorite_service
from app.utils.response import success_response

router = APIRouter(prefix="/favorites", tags=["收藏"])


# TODO: 接入真实用户认证后，替换 current_user_id
async def _get_user_id() -> int:
    """临时：获取当前用户 ID（后续替换为 JWT 认证）"""
    return 1


@router.get("")
async def get_favorites(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """获取我的收藏列表"""
    favorites = await favorite_service.get_favorites(db, user_id)
    return success_response({"favorites": favorites})


@router.post("")
async def add_favorite(
    city_id: int = Query(..., description="城市ID"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """添加城市收藏"""
    ok = await favorite_service.add_favorite(db, user_id, city_id)
    if not ok:
        return success_response(None, message="已收藏过该城市")
    return success_response(None, message="收藏成功")


@router.delete("/{city_id}")
async def remove_favorite(
    city_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """删除城市收藏"""
    ok = await favorite_service.remove_favorite(db, user_id, city_id)
    if not ok:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("收藏不存在")
    return success_response(None, message="已取消收藏")


@router.put("/sort")
async def sort_favorites(
    city_ids: list[int] = Query(..., description="排序后的城市 ID 列表"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(_get_user_id),
):
    """更新收藏排序"""
    await favorite_service.sort_favorites(db, user_id, city_ids)
    return success_response(None, message="排序已更新")
