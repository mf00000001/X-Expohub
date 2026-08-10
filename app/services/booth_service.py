"""展位服务（异步版）"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, ForbiddenException, NotFoundException
from app.models.booth import Booth
from app.models.exhibition import Exhibition
from app.schemas.booth import BoothCreate, BoothUpdate


async def create_booth(db: AsyncSession, data: BoothCreate) -> Booth:
    """
    创建展位

    Args:
        db: 异步数据库会话
        data: 展位创建数据

    Returns:
        创建的展位对象
    """
    booth = Booth(
        exhibition_id=data.exhibition_id,
        booth_number=data.booth_number,
        name=data.name,
        description=data.description,
        area=data.area,
        price=data.price,
        floor=data.floor,
        zone=data.zone,
        status="available",
    )
    db.add(booth)

    # 更新展会的总展位数
    result = await db.execute(
        select(Exhibition).where(Exhibition.id == data.exhibition_id)
    )
    exhibition = result.scalar_one_or_none()
    if exhibition:
        exhibition.total_booths = (exhibition.total_booths or 0) + 1
        exhibition.available_booths = (exhibition.available_booths or 0) + 1

    await db.commit()
    await db.refresh(booth)
    return booth


async def get_booth_by_id(db: AsyncSession, booth_id: int) -> Booth:
    """
    根据ID获取展位

    Args:
        db: 异步数据库会话
        booth_id: 展位ID

    Returns:
        展位对象
    """
    result = await db.execute(
        select(Booth).where(Booth.id == booth_id)
    )
    booth = result.scalar_one_or_none()
    if booth is None:
        raise NotFoundException("展位不存在")
    return booth


async def update_booth(db: AsyncSession, booth_id: int, data: BoothUpdate) -> Booth:
    """
    更新展位

    Args:
        db: 异步数据库会话
        booth_id: 展位ID
        data: 更新数据

    Returns:
        更新后的展位对象
    """
    booth = await get_booth_by_id(db, booth_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(booth, field, value)
    await db.commit()
    await db.refresh(booth)
    return booth


async def book_booth(db: AsyncSession, booth_id: int, exhibitor_id: int) -> Booth:
    """
    预订展位

    Args:
        db: 异步数据库会话
        booth_id: 展位ID
        exhibitor_id: 展商用户ID

    Returns:
        更新后的展位对象
    """
    booth = await get_booth_by_id(db, booth_id)

    if booth.status != "available":
        raise BusinessException("展位不可预订")

    booth.status = "reserved"
    booth.exhibitor_id = exhibitor_id

    # 更新展会的可用展位数
    result = await db.execute(
        select(Exhibition).where(Exhibition.id == booth.exhibition_id)
    )
    exhibition = result.scalar_one_or_none()
    if exhibition and exhibition.available_booths > 0:
        exhibition.available_booths -= 1

    await db.commit()
    await db.refresh(booth)
    return booth


async def get_booths_by_exhibition(
    db: AsyncSession,
    exhibition_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Booth], int]:
    """
    获取展位列表

    Args:
        db: 异步数据库会话
        exhibition_id: 展会ID筛选
        status: 状态筛选
        page: 页码
        page_size: 每页数量

    Returns:
        (展位列表, 总数)
    """
    stmt = select(Booth)

    if exhibition_id:
        stmt = stmt.where(Booth.exhibition_id == exhibition_id)
    if status:
        stmt = stmt.where(Booth.status == status)

    # count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # paginated
    stmt = stmt.order_by(Booth.booth_number).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    booths = result.scalars().all()

    return list(booths), total
