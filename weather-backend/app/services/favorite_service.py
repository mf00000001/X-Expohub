"""天气查询平台 - 收藏服务"""

from __future__ import annotations

from sqlalchemy import and_, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserFavorite


class FavoriteService:
    """用户收藏服务"""

    async def get_favorites(self, db: AsyncSession, user_id: int) -> list[dict]:
        """获取用户收藏列表"""
        stmt = (
            select(UserFavorite)
            .where(UserFavorite.user_id == user_id)
            .order_by(UserFavorite.sort_order)
        )
        result = await db.execute(stmt)
        favorites = result.scalars().all()
        return [
            {
                "id": f.id,
                "city_id": f.city_id,
                "sort_order": f.sort_order,
                "is_default": f.is_default,
            }
            for f in favorites
        ]

    async def add_favorite(
        self, db: AsyncSession, user_id: int, city_id: int
    ) -> bool:
        """添加收藏（返回 True=新增, False=已存在）"""
        existing = await db.execute(
            select(UserFavorite).where(
                and_(UserFavorite.user_id == user_id, UserFavorite.city_id == city_id)
            )
        )
        if existing.scalar_one_or_none():
            return False

        # 获取当前最大排序
        result = await db.execute(
            select(UserFavorite).where(UserFavorite.user_id == user_id)
        )
        count = len(result.scalars().all())

        fav = UserFavorite(
            user_id=user_id,
            city_id=city_id,
            sort_order=count + 1,
            is_default=(count == 0),  # 第一个自动设为默认
        )
        db.add(fav)
        await db.flush()
        return True

    async def remove_favorite(
        self, db: AsyncSession, user_id: int, city_id: int
    ) -> bool:
        """删除收藏"""
        stmt = delete(UserFavorite).where(
            and_(UserFavorite.user_id == user_id, UserFavorite.city_id == city_id)
        )
        result = await db.execute(stmt)
        return result.rowcount > 0

    async def sort_favorites(
        self, db: AsyncSession, user_id: int, city_ids: list[int]
    ) -> None:
        """更新排序"""
        for idx, city_id in enumerate(city_ids):
            result = await db.execute(
                select(UserFavorite).where(
                    and_(UserFavorite.user_id == user_id, UserFavorite.city_id == city_id)
                )
            )
            fav = result.scalar_one_or_none()
            if fav:
                fav.sort_order = idx + 1
        await db.flush()


favorite_service = FavoriteService()
