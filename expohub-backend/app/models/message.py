"""
消息 & 会话表（Message / Conversation）

对应前端 API: expo-hub-uniapp/src/api/message.ts

前端 Message 接口字段：
  id, conversation_id, sender_id, sender_name?,
  receiver_id, title, content, is_read, read_at, created_at

前端 Conversation 接口字段：
  id, participants, last_message?, unread_count, updated_at
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Text, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Conversation(Base):
    """会话表 — 两个用户之间的对话"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 参与方 ----
    user1_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="参与方 1 用户 ID"
    )
    user2_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="参与方 2 用户 ID"
    )

    # ---- 统计 ----
    unread_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="未读消息数"
    )

    # ---- 时间戳 ----
    updated_at: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="最后更新时间（ISO 8601 字符串）"
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, users={self.user1_id}<->{self.user2_id})>"


class Message(Base):
    """消息表 — 会话中的单条消息"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 所属会话 ----
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=False, index=True,
        comment="所属会话 ID"
    )

    # ---- 收发方 ----
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="发送者用户 ID"
    )
    sender_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="发送者名称（冗余）"
    )
    receiver_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="接收者用户 ID"
    )

    # ---- 消息标题 ----
    title: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="消息标题"
    )

    # ---- 消息内容 ----
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="消息内容"
    )

    # ---- 状态 ----
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True,
        comment="是否已读"
    )
    read_at: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="阅读时间（ISO 8601 字符串）"
    )

    # ---- 时间戳 ----
    created_at: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="发送时间（ISO 8601 字符串）"
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, conv={self.conversation_id}, read={self.is_read})>"
