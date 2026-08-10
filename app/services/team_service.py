"""团队服务：团队管理（异步版）"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, NotFoundException
from app.models.team import Team, TeamMember
from app.models.user import User
from app.schemas.team import TeamCreate, TeamUpdate


async def create_team(db: AsyncSession, boss_id: int, data: TeamCreate) -> Team:
    """
    创建团队

    Args:
        db: 异步数据库会话
        boss_id: 老板用户ID
        data: 团队数据

    Returns:
        创建的团队对象
    """
    team = Team(
        boss_id=boss_id,
        name=data.name,
        description=data.description,
    )
    db.add(team)
    await db.flush()

    # 创建者自动成为团队管理员
    member = TeamMember(
        team_id=team.id,
        user_id=boss_id,
        role_in_team="admin",
    )
    db.add(member)
    await db.commit()
    await db.refresh(team)
    return team


async def get_team_by_id(db: AsyncSession, team_id: int) -> Team:
    """
    根据ID获取团队

    Args:
        db: 异步数据库会话
        team_id: 团队ID

    Returns:
        团队对象
    """
    result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()
    if team is None:
        raise NotFoundException("团队不存在")
    return team


async def update_team(db: AsyncSession, team_id: int, boss_id: int, data: TeamUpdate) -> Team:
    """
    更新团队信息

    Args:
        db: 异步数据库会话
        team_id: 团队ID
        boss_id: 老板用户ID
        data: 更新数据

    Returns:
        更新后的团队对象
    """
    team = await get_team_by_id(db, team_id)

    if team.boss_id != boss_id:
        raise BusinessException("无权操作此团队")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(team, field, value)

    await db.commit()
    await db.refresh(team)
    return team


async def delete_team(db: AsyncSession, team_id: int, boss_id: int) -> None:
    """
    删除团队

    Args:
        db: 异步数据库会话
        team_id: 团队ID
        boss_id: 老板用户ID
    """
    team = await get_team_by_id(db, team_id)

    if team.boss_id != boss_id:
        raise BusinessException("无权删除此团队")

    await db.delete(team)
    await db.commit()


async def get_boss_teams(db: AsyncSession, boss_id: int) -> list[Team]:
    """
    获取老板的所有团队

    Args:
        db: 异步数据库会话
        boss_id: 老板用户ID

    Returns:
        团队列表
    """
    result = await db.execute(
        select(Team)
        .where(Team.boss_id == boss_id)
        .order_by(Team.created_at.desc())
    )
    return list(result.scalars().all())


async def add_member(db: AsyncSession, team_id: int, boss_id: int, user_id: int, role: str = "member") -> TeamMember:
    """
    添加团队成员

    Args:
        db: 异步数据库会话
        team_id: 团队ID
        boss_id: 老板用户ID
        user_id: 成员用户ID
        role: 团队角色

    Returns:
        团队成员记录

    Raises:
        BusinessException: 用户已在团队中
    """
    team = await get_team_by_id(db, team_id)

    if team.boss_id != boss_id:
        raise BusinessException("无权操作此团队")

    # 检查用户是否存在
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundException("用户不存在")

    # 检查是否已在团队中
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise BusinessException("该用户已在团队中")

    member = TeamMember(
        team_id=team_id,
        user_id=user_id,
        role_in_team=role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def remove_member(db: AsyncSession, team_id: int, boss_id: int, user_id: int) -> None:
    """
    移除团队成员

    Args:
        db: 异步数据库会话
        team_id: 团队ID
        boss_id: 老板用户ID
        user_id: 成员用户ID
    """
    team = await get_team_by_id(db, team_id)

    if team.boss_id != boss_id:
        raise BusinessException("无权操作此团队")

    result = await db.execute(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise NotFoundException("团队成员不存在")

    await db.delete(member)
    await db.commit()


async def get_team_members(db: AsyncSession, team_id: int) -> list[TeamMember]:
    """
    获取团队成员列表

    Args:
        db: 异步数据库会话
        team_id: 团队ID

    Returns:
        团队成员列表
    """
    result = await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id)
    )
    return list(result.scalars().all())
