"""
展会报名表（Registration）

对应前端 API: expo-hub-frontend/src/api/registration.ts

前端 RegistrationItem 接口字段：
  id, visitor_id, exhibition_id, is_favorite, is_registered,
  ticket_code?, check_in_at?, created_at, exhibition?
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Registration(Base):
    """展会报名表 — 用户报名参加展会"""
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 关联 ----
    visitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="报名用户 ID"
    )
    exhibition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=False, index=True,
        comment="展会 ID"
    )

    # ---- 报名状态 ----
    is_favorite: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否收藏"
    )
    is_registered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否已报名"
    )

    # ---- 票务 ----
    ticket_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, unique=True, comment="电子票码"
    )
    check_in_at: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="签到时间（ISO 8601 字符串）"
    )

    # ---- 时间戳 ----
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="报名时间"
    )

    def __repr__(self) -> str:
        return f"<Registration(id={self.id}, user={self.visitor_id}, exh={self.exhibition_id})>"
