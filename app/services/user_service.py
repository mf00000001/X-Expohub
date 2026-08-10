"""用户服务：用户信息管理（异步版）"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.user import UserProfileUpdate


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    """
    根据ID获取用户

    Args:
        db: 异步数据库会话
        user_id: 用户ID

    Returns:
        用户对象

    Raises:
        NotFoundException: 用户不存在
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundException("用户不存在")
    return user


async def update_user_profile(
    db: AsyncSession,
    user_id: int,
    data: UserProfileUpdate,
) -> User:
    """
    更新用户资料

    Args:
        db: 异步数据库会话
        user_id: 用户ID
        data: 更新数据

    Returns:
        更新后的用户对象
    """
    user = await get_user_by_id(db, user_id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


async def get_user_list(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    role: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
) -> tuple[list[User], int]:
    """
    获取用户列表（管理用）

    Args:
        db: 异步数据库会话
        page: 页码
        page_size: 每页数量
        role: 角色筛选
        status: 状态筛选
        keyword: 关键词搜索

    Returns:
        (用户列表, 总数)
    """
    stmt = select(User).where(User.deleted_at.is_(None))

    if role:
        stmt = stmt.where(User.role == role)
    if status:
        stmt = stmt.where(User.status == status)
    if keyword:
        stmt = stmt.where(
            (User.username.ilike(f"%{keyword}%")) |
            (User.email.ilike(f"%{keyword}%")) |
            (User.nickname.ilike(f"%{keyword}%"))
        )

    # count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # paginated
    stmt = stmt.order_by(User.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    users = result.scalars().all()

    return list(users), total
