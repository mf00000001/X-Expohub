"""展会预约表（Appointment）— 买家预约展商线下见面

V2.9 原为内存存储（appointments_db 列表），本模型将其落库，
支持持久化、事务与后续配对码核销状态机扩展。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Appointment(Base):
    """展会预约表 — 买家预约展商在展会现场见面"""
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 关联 ----
    buyer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="买家用户 ID"
    )
    exhibitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="展商用户 ID"
    )
    exhibition_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=True, index=True,
        comment="展会 ID"
    )

    # ---- 预约信息 ----
    time_slot: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="时段：上午/下午/全天"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="confirmed",
        comment="状态：pending/confirmed/rejected/redeemed/no_show"
    )

    # ---- 冗余名称（展示用） ----
    buyer_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    exhibitor_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ---- 时间戳 ----
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="预约时间"
    )

    def __repr__(self) -> str:
        return f"<Appointment(id={self.id}, buyer={self.buyer_id}, exhibitor={self.exhibitor_id})>"
