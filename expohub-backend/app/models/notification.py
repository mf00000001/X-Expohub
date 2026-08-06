"""V2.4: 通知系统 — 撮合引擎的最后一环"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="接收通知的用户ID")
    type: Mapped[str] = mapped_column(String(30), nullable=False, comment="通知类型: match/bid/favorite/message/system")
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="通知标题")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="通知内容")
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="点击跳转链接")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已读")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


def notify(db, user_id: int, type: str, title: str, content: str = None, link: str = None):
    """发送通知的便捷函数"""
    try:
        n = Notification(user_id=user_id, type=type, title=title, content=content, link=link)
        db.add(n)
        db.commit()
    except: pass
