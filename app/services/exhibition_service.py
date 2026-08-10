"""展会服务：展会管理（异步版）"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, ForbiddenException, NotFoundException
from app.models.exhibition import Exhibition
from app.models.user import User
from app.schemas.exhibition import ExhibitionCreate, ExhibitionUpdate


async def create_exhibition(db: AsyncSession, organizer_id: int, data: ExhibitionCreate) -> Exhibition:
    """
    创建展会

    Args:
        db: 异步数据库会话
        organizer_id: 主办方用户ID
        data: 展会创建数据

    Returns:
        创建的展会对象
    """
    exhibition = Exhibition(
        name=data.name,
        short_name=data.short_name,
        description=data.description,
        cover_url=data.cover_url,
        start_date=datetime.fromisoformat(data.start_date) if data.start_date else datetime.utcnow(),
        end_date=datetime.fromisoformat(data.end_date) if data.end_date else datetime.utcnow(),
        registration_deadline=datetime.fromisoformat(data.registration_deadline) if data.registration_deadline else None,
        venue=data.venue,
        address=data.address,
        city=data.city,
        organizer_id=organizer_id,
        status="draft",
        total_booths=data.total_booths,
        available_booths=data.total_booths,
    )
    db.add(exhibition)
    await db.commit()
    await db.refresh(exhibition)
    return exhibition


async def get_exhibition_by_id(db: AsyncSession, exhibition_id: int) -> Exhibition:
    """
    根据ID获取展会

    Args:
        db: 异步数据库会话
        exhibition_id: 展会ID

    Returns:
        展会对象
    """
    result = await db.execute(
        select(Exhibition).where(Exhibition.id == exhibition_id)
    )
    exhibition = result.scalar_one_or_none()
    if exhibition is None:
        raise NotFoundException("展会不存在")
    return exhibition


async def update_exhibition(
    db: AsyncSession,
    exhibition_id: int,
    organizer_id: int,
    data: ExhibitionUpdate,
) -> Exhibition:
    """
    更新展会

    Args:
        db: 异步数据库会话
        exhibition_id: 展会ID
        organizer_id: 主办方用户ID
        data: 更新数据

    Returns:
        更新后的展会对象
    """
    exhibition = await get_exhibition_by_id(db, exhibition_id)

    if exhibition.organizer_id != organizer_id:
        raise ForbiddenException("无权操作此展会")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in ("start_date", "end_date", "registration_deadline") and value:
            setattr(exhibition, field, datetime.fromisoformat(value))
        elif value is not None:
            setattr(exhibition, field, value)

    await db.commit()
    await db.refresh(exhibition)
    return exhibition


async def publish_exhibition(db: AsyncSession, exhibition_id: int, organizer_id: int) -> Exhibition:
    """
    发布展会（提交审批）

    Args:
        db: 异步数据库会话
        exhibition_id: 展会ID
        organizer_id: 主办方用户ID

    Returns:
        更新后的展会对象
    """
    exhibition = await get_exhibition_by_id(db, exhibition_id)

    if exhibition.organizer_id != organizer_id:
        raise ForbiddenException("无权操作此展会")

    if exhibition.status != "draft":
        raise BusinessException(f"当前状态不允许发布: {exhibition.status}")

    exhibition.status = "pending"
    await db.commit()
    await db.refresh(exhibition)
    return exhibition


async def approve_exhibition(
    db: AsyncSession,
    exhibition_id: int,
    approver_id: int,
    approved: bool,
    reject_reason: Optional[str] = None,
) -> Exhibition:
    """
    审批展会（老板操作）

    Args:
        db: 异步数据库会话
        exhibition_id: 展会ID
        approver_id: 审批人ID
        approved: 是否通过
        reject_reason: 驳回原因

    Returns:
        更新后的展会对象
    """
    exhibition = await get_exhibition_by_id(db, exhibition_id)

    if exhibition.status != "pending":
        raise BusinessException(f"当前状态不允许审批: {exhibition.status}")

    if approved:
        exhibition.status = "published"
        exhibition.approved_by = approver_id
        exhibition.approved_at = datetime.utcnow()
    else:
        exhibition.status = "draft"
        exhibition.reject_reason = reject_reason

    await db.commit()
    await db.refresh(exhibition)
    return exhibition


async def get_exhibition_list(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    city: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    organizer_id: Optional[int] = None,
) -> tuple[list[Exhibition], int]:
    """
    获取展会列表

    Args:
        db: 异步数据库会话
        page: 页码
        page_size: 每页数量
        city: 城市筛选
        status: 状态筛选
        keyword: 关键词搜索
        organizer_id: 主办方ID筛选

    Returns:
        (展会列表, 总数)
    """
    stmt = select(Exhibition)

    if city:
        stmt = stmt.where(Exhibition.city == city)
    if status:
        stmt = stmt.where(Exhibition.status == status)
    if keyword:
        stmt = stmt.where(Exhibition.name.ilike(f"%{keyword}%"))
    if organizer_id:
        stmt = stmt.where(Exhibition.organizer_id == organizer_id)

    # count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # paginated query
    stmt = stmt.order_by(Exhibition.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    exhibitions = result.scalars().all()

    return list(exhibitions), total
