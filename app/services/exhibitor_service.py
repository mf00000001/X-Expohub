"""展商服务：展商信息与展品管理（异步版）"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, ForbiddenException, NotFoundException
from app.models.booth import Booth, Product
from app.models.exhibitor import Exhibitor
from app.schemas.exhibitor import ExhibitorCreate, ExhibitorUpdate, ProductCreate, ProductUpdate


async def create_exhibitor_info(db: AsyncSession, user_id: int, data: ExhibitorCreate) -> Exhibitor:
    """
    创建/完善展商信息

    Args:
        db: 异步数据库会话
        user_id: 用户ID
        data: 展商信息

    Returns:
        展商信息对象
    """
    result = await db.execute(
        select(Exhibitor).where(Exhibitor.user_id == user_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise BusinessException("展商信息已存在")

    exhibitor = Exhibitor(
        user_id=user_id,
        company_name=data.company_name,
        company_short_name=data.company_short_name,
        logo_url=data.logo_url,
        business_scope=data.business_scope,
        website=data.website,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        status="pending",
    )
    db.add(exhibitor)
    await db.commit()
    await db.refresh(exhibitor)
    return exhibitor


async def get_exhibitor_info(db: AsyncSession, user_id: int) -> Exhibitor:
    """
    获取展商信息

    Args:
        db: 异步数据库会话
        user_id: 用户ID

    Returns:
        展商信息对象
    """
    result = await db.execute(
        select(Exhibitor).where(Exhibitor.user_id == user_id)
    )
    exhibitor = result.scalar_one_or_none()
    if exhibitor is None:
        raise NotFoundException("展商信息不存在")
    return exhibitor


async def update_exhibitor_info(
    db: AsyncSession,
    user_id: int,
    data: ExhibitorUpdate,
) -> Exhibitor:
    """
    更新展商信息

    Args:
        db: 异步数据库会话
        user_id: 用户ID
        data: 更新数据

    Returns:
        更新后的展商信息
    """
    exhibitor = await get_exhibitor_info(db, user_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exhibitor, field, value)
    await db.commit()
    await db.refresh(exhibitor)
    return exhibitor


async def create_product(db: AsyncSession, exhibitor_id: int, data: ProductCreate) -> Product:
    """
    创建展品

    Args:
        db: 异步数据库会话
        exhibitor_id: 展商用户ID
        data: 展品数据

    Returns:
        创建的展品对象
    """
    product = Product(
        exhibitor_id=exhibitor_id,
        name=data.name,
        description=data.description,
        category=data.category,
        images=data.images,
        price=data.price,
        specs=data.specs,
        booth_id=data.booth_id,
        exhibition_id=data.exhibition_id,
        status="draft",
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


async def get_product_by_id(db: AsyncSession, product_id: int) -> Product:
    """
    根据ID获取展品

    Args:
        db: 异步数据库会话
        product_id: 展品ID

    Returns:
        展品对象
    """
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise NotFoundException("展品不存在")
    return product


async def update_product(
    db: AsyncSession,
    product_id: int,
    exhibitor_id: int,
    data: ProductUpdate,
) -> Product:
    """
    更新展品

    Args:
        db: 异步数据库会话
        product_id: 展品ID
        exhibitor_id: 展商用户ID
        data: 更新数据

    Returns:
        更新后的展品对象
    """
    product = await get_product_by_id(db, product_id)

    if product.exhibitor_id != exhibitor_id:
        raise ForbiddenException("无权操作此展品")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: int, exhibitor_id: int) -> None:
    """
    删除展品

    Args:
        db: 异步数据库会话
        product_id: 展品ID
        exhibitor_id: 展商用户ID
    """
    product = await get_product_by_id(db, product_id)

    if product.exhibitor_id != exhibitor_id:
        raise ForbiddenException("无权删除此展品")

    await db.delete(product)
    await db.commit()


async def get_products_by_exhibitor(
    db: AsyncSession,
    exhibitor_id: int,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Product], int]:
    """
    获取展商的展品列表

    Args:
        db: 异步数据库会话
        exhibitor_id: 展商用户ID
        page: 页码
        page_size: 每页数量

    Returns:
        (展品列表, 总数)
    """
    stmt = select(Product).where(Product.exhibitor_id == exhibitor_id)

    # count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # paginated
    stmt = stmt.order_by(Product.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    products = result.scalars().all()

    return list(products), total
