"""消息服务：在线沟通（异步版）"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.message import Message
from app.schemas.message import MessageCreate


async def send_message(db: AsyncSession, sender_id: int, data: MessageCreate) -> Message:
    """
    发送消息

    Args:
        db: 异步数据库会话
        sender_id: 发送者用户ID
        data: 消息数据

    Returns:
        创建的消息对象
    """
    message = Message(
        sender_id=sender_id,
        receiver_id=data.receiver_id,
        title=data.title,
        content=data.content,
        is_read=False,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def get_message_by_id(db: AsyncSession, message_id: int) -> Message:
    """
    根据ID获取消息

    Args:
        db: 异步数据库会话
        message_id: 消息ID

    Returns:
        消息对象
    """
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise NotFoundException("消息不存在")
    return message


async def mark_as_read(db: AsyncSession, message_id: int, user_id: int) -> Message:
    """
    标记消息为已读

    Args:
        db: 异步数据库会话
        message_id: 消息ID
        user_id: 用户ID（接收者）

    Returns:
        更新后的消息对象
    """
    message = await get_message_by_id(db, message_id)

    if message.receiver_id != user_id:
        return message  # 只有接收者可以标记已读

    if not message.is_read:
        message.is_read = True
        message.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(message)

    return message


async def get_user_messages(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
) -> tuple[list[Message], int]:
    """
    获取用户的消息列表

    Args:
        db: 异步数据库会话
        user_id: 用户ID
        page: 页码
        page_size: 每页数量
        unread_only: 仅查看未读

    Returns:
        (消息列表, 总数)
    """
    stmt = select(Message).where(
        (Message.sender_id == user_id) | (Message.receiver_id == user_id)
    )

    if unread_only:
        stmt = stmt.where(Message.receiver_id == user_id, Message.is_read == False)

    # count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # paginated
    stmt = stmt.order_by(Message.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    messages = result.scalars().all()

    return list(messages), total


async def get_conversation(
    db: AsyncSession,
    user_id: int,
    other_user_id: int,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Message], int]:
    """
    获取两个用户之间的会话

    Args:
        db: 异步数据库会话
        user_id: 当前用户ID
        other_user_id: 对方用户ID
        page: 页码
        page_size: 每页数量

    Returns:
        (消息列表, 总数)
    """
    stmt = select(Message).where(
        (
            (Message.sender_id == user_id) & (Message.receiver_id == other_user_id)
        ) | (
            (Message.sender_id == other_user_id) & (Message.receiver_id == user_id)
        )
    )

    # count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # paginated
    stmt = stmt.order_by(Message.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    messages = result.scalars().all()

    return list(messages), total


async def get_unread_count(db: AsyncSession, user_id: int) -> int:
    """
    获取用户未读消息数

    Args:
        db: 异步数据库会话
        user_id: 用户ID

    Returns:
        未读消息数
    """
    result = await db.execute(
        select(func.count(Message.id)).where(
            Message.receiver_id == user_id,
            Message.is_read == False,
        )
    )
    return result.scalar() or 0
