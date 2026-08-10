"""采购需求服务（异步版）"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, ForbiddenException, NotFoundException
from app.models.procurement import ProcurementMatch, ProcurementRequest
from app.schemas.procurement import MatchCreate, ProcurementCreate, ProcurementUpdate


async def create_procurement(
    db: AsyncSession,
    visitor_id: int,
    data: ProcurementCreate,
) -> ProcurementRequest:
    """
    发布采购需求

    Args:
        db: 异步数据库会话
        visitor_id: 游客用户ID
        data: 采购需求数据

    Returns:
        创建的采购需求对象
    """
    procurement = ProcurementRequest(
        visitor_id=visitor_id,
        title=data.title,
        description=data.description,
        category=data.category,
        budget_min=data.budget_min,
        budget_max=data.budget_max,
        deadline=datetime.fromisoformat(data.deadline) if data.deadline else None,
        status="pending",
    )
    db.add(procurement)
    await db.commit()
    await db.refresh(procurement)
    return procurement


async def get_procurement_by_id(db: AsyncSession, procurement_id: int) -> ProcurementRequest:
    """
    根据ID获取采购需求

    Args:
        db: 异步数据库会话
        procurement_id: 采购需求ID

    Returns:
        采购需求对象
    """
    result = await db.execute(
        select(ProcurementRequest).where(ProcurementRequest.id == procurement_id)
    )
    procurement = result.scalar_one_or_none()
    if procurement is None:
        raise NotFoundException("采购需求不存在")
    return procurement


async def update_procurement(
    db: AsyncSession,
    procurement_id: int,
    visitor_id: int,
    data: ProcurementUpdate,
) -> ProcurementRequest:
    """
    更新采购需求

    Args:
        db: 异步数据库会话
        procurement_id: 采购需求ID
        visitor_id: 游客用户ID
        data: 更新数据

    Returns:
        更新后的采购需求对象
    """
    procurement = await get_procurement_by_id(db, procurement_id)

    if procurement.visitor_id != visitor_id:
        raise ForbiddenException("无权操作此采购需求")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "deadline" and value:
            setattr(procurement, field, datetime.fromisoformat(value))
        elif value is not None:
            setattr(procurement, field, value)

    await db.commit()
    await db.refresh(procurement)
    return procurement


async def get_procurement_list(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    category: Optional[str] = None,
    visitor_id: Optional[int] = None,
) -> tuple[list[ProcurementRequest], int]:
    """
    获取采购需求列表

    Args:
        db: 异步数据库会话
        page: 页码
        page_size: 每页数量
        status: 状态筛选
        category: 品类筛选
        visitor_id: 发布者ID筛选

    Returns:
        (采购需求列表, 总数)
    """
    stmt = select(ProcurementRequest)

    if status:
        stmt = stmt.where(ProcurementRequest.status == status)
    if category:
        stmt = stmt.where(ProcurementRequest.category == category)
    if visitor_id:
        stmt = stmt.where(ProcurementRequest.visitor_id == visitor_id)

    # count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # paginated
    stmt = stmt.order_by(ProcurementRequest.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    procurements = result.scalars().all()

    return list(procurements), total


async def create_match(db: AsyncSession, exhibitor_id: int, data: MatchCreate) -> ProcurementMatch:
    """
    展商匹配采购需求

    Args:
        db: 异步数据库会话
        exhibitor_id: 展商用户ID
        data: 匹配数据

    Returns:
        创建的匹配记录

    Raises:
        BusinessException: 已匹配过或采购需求状态不允许
    """
    procurement = await get_procurement_by_id(db, data.procurement_id)

    if procurement.status not in ("pending", "matched"):
        raise BusinessException("当前采购需求状态不允许匹配")

    # 检查是否已匹配过
    existing_result = await db.execute(
        select(ProcurementMatch).where(
            ProcurementMatch.procurement_id == data.procurement_id,
            ProcurementMatch.exhibitor_id == exhibitor_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise BusinessException("您已匹配过此采购需求")

    match = ProcurementMatch(
        procurement_id=data.procurement_id,
        exhibitor_id=exhibitor_id,
        message=data.message,
        quoted_price=data.quoted_price,
    )
    db.add(match)

    # 更新采购需求状态
    if procurement.status == "pending":
        procurement.status = "matched"

    await db.commit()
    await db.refresh(match)
    return match


async def get_matches_for_procurement(
    db: AsyncSession,
    procurement_id: int,
) -> list[ProcurementMatch]:
    """
    获取采购需求的匹配列表

    Args:
        db: 异步数据库会话
        procurement_id: 采购需求ID

    Returns:
        匹配记录列表
    """
    result = await db.execute(
        select(ProcurementMatch)
        .where(ProcurementMatch.procurement_id == procurement_id)
        .order_by(ProcurementMatch.created_at.desc())
    )
    return list(result.scalars().all())


async def accept_match(db: AsyncSession, match_id: int, visitor_id: int) -> ProcurementMatch:
    """
    采购方接受匹配

    Args:
        db: 异步数据库会话
        match_id: 匹配记录ID
        visitor_id: 游客用户ID

    Returns:
        更新后的匹配记录
    """
    result = await db.execute(
        select(ProcurementMatch).where(ProcurementMatch.id == match_id)
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise NotFoundException("匹配记录不存在")

    procurement = await get_procurement_by_id(db, match.procurement_id)
    if procurement.visitor_id != visitor_id:
        raise ForbiddenException("无权操作此匹配")

    match.is_accepted = True
    procurement.status = "completed"
    await db.commit()
    await db.refresh(match)
    return match
