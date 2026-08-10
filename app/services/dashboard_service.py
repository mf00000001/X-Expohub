"""数据报表服务（异步版）"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booth import Booth, Product
from app.models.exhibition import Exhibition
from app.models.exhibitor import Exhibitor
from app.models.message import Message
from app.models.procurement import ProcurementMatch, ProcurementRequest
from app.models.user import User
from app.schemas.dashboard import (
    DashboardResponse,
    ExhibitionStats,
    ExhibitorStats,
    MessageStats,
    ProcurementStats,
)


async def get_dashboard_stats(db: AsyncSession) -> DashboardResponse:
    """
    获取仪表盘统计数据

    Args:
        db: 异步数据库会话

    Returns:
        仪表盘数据
    """
    return DashboardResponse(
        exhibition_stats=await get_exhibition_stats(db),
        exhibitor_stats=await get_exhibitor_stats(db),
        procurement_stats=await get_procurement_stats(db),
        message_stats=await get_message_stats(db),
    )


async def get_exhibition_stats(db: AsyncSession) -> ExhibitionStats:
    """
    获取展会统计

    Args:
        db: 异步数据库会话

    Returns:
        展会统计数据
    """
    total_result = await db.execute(select(func.count(Exhibition.id)))
    total = total_result.scalar() or 0

    published_result = await db.execute(
        select(func.count(Exhibition.id)).where(Exhibition.status == "published")
    )
    published = published_result.scalar() or 0

    ongoing_result = await db.execute(
        select(func.count(Exhibition.id)).where(Exhibition.status == "ongoing")
    )
    ongoing = ongoing_result.scalar() or 0

    ended_result = await db.execute(
        select(func.count(Exhibition.id)).where(Exhibition.status == "ended")
    )
    ended = ended_result.scalar() or 0

    draft_result = await db.execute(
        select(func.count(Exhibition.id)).where(Exhibition.status == "draft")
    )
    draft = draft_result.scalar() or 0

    visitors_result = await db.execute(select(func.sum(Exhibition.visitor_count)))
    total_visitors = visitors_result.scalar() or 0

    booths_total_result = await db.execute(select(func.sum(Exhibition.total_booths)))
    total_booths = booths_total_result.scalar() or 0

    occupied_result = await db.execute(
        select(func.count(Booth.id)).where(Booth.status == "occupied")
    )
    occupied_booths = occupied_result.scalar() or 0

    return ExhibitionStats(
        total_exhibitions=total,
        published_count=published,
        ongoing_count=ongoing,
        ended_count=ended,
        draft_count=draft,
        total_visitors=total_visitors,
        total_booths=total_booths,
        occupied_booths=occupied_booths,
    )


async def get_exhibitor_stats(db: AsyncSession) -> ExhibitorStats:
    """
    获取展商统计

    Args:
        db: 异步数据库会话

    Returns:
        展商统计数据
    """
    total_result = await db.execute(select(func.count(Exhibitor.id)))
    total = total_result.scalar() or 0

    approved_result = await db.execute(
        select(func.count(Exhibitor.id)).where(Exhibitor.status == "approved")
    )
    approved = approved_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(Exhibitor.id)).where(Exhibitor.status == "pending")
    )
    pending = pending_result.scalar() or 0

    total_products_result = await db.execute(select(func.count(Product.id)))
    total_products = total_products_result.scalar() or 0

    active_products_result = await db.execute(
        select(func.count(Product.id)).where(Product.status == "published")
    )
    active_products = active_products_result.scalar() or 0

    return ExhibitorStats(
        total_exhibitors=total,
        approved_count=approved,
        pending_count=pending,
        total_products=total_products,
        active_products=active_products,
    )


async def get_procurement_stats(db: AsyncSession) -> ProcurementStats:
    """
    获取采购需求统计

    Args:
        db: 异步数据库会话

    Returns:
        采购需求统计数据
    """
    total_result = await db.execute(select(func.count(ProcurementRequest.id)))
    total = total_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(ProcurementRequest.id)).where(ProcurementRequest.status == "pending")
    )
    pending = pending_result.scalar() or 0

    matched_result = await db.execute(
        select(func.count(ProcurementRequest.id)).where(ProcurementRequest.status == "matched")
    )
    matched = matched_result.scalar() or 0

    completed_result = await db.execute(
        select(func.count(ProcurementRequest.id)).where(ProcurementRequest.status == "completed")
    )
    completed = completed_result.scalar() or 0

    total_matches_result = await db.execute(select(func.count(ProcurementMatch.id)))
    total_matches = total_matches_result.scalar() or 0

    return ProcurementStats(
        total_requests=total,
        pending_count=pending,
        matched_count=matched,
        completed_count=completed,
        total_matches=total_matches,
    )


async def get_message_stats(db: AsyncSession) -> MessageStats:
    """
    获取消息统计

    Args:
        db: 异步数据库会话

    Returns:
        消息统计数据
    """
    total_result = await db.execute(select(func.count(Message.id)))
    total = total_result.scalar() or 0

    unread_result = await db.execute(
        select(func.count(Message.id)).where(Message.is_read == False)
    )
    unread = unread_result.scalar() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(Message.id)).where(Message.created_at >= today_start)
    )
    today_count = today_result.scalar() or 0

    return MessageStats(
        total_messages=total,
        unread_count=unread,
        today_count=today_count,
    )
