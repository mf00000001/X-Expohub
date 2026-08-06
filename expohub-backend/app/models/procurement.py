"""
采购需求表（Procurement）

对应前端 API: expo-hub-uniapp/src/api/procurement.ts

前端 Procurement 接口字段：
  id, exhibition_id?, exhibition_title?, purchaser_id?, purchaser_name?,
  title, description, category?, quantity?, unit?, budget?,
  deadline?, status,
  created_at?, updated_at?
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Procurement(Base):
    """采购需求表 — 游客发布采购需求，展商可匹配"""
    __tablename__ = "procurements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 关联 ----
    exhibition_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=True, index=True,
        comment="关联展会 ID"
    )
    exhibition_title: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="展会标题（冗余）"
    )
    purchaser_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
        comment="发布者（采购方）用户 ID"
    )
    purchaser_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="采购方名称（冗余）"
    )

    # ---- 采购信息 ----
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True, comment="采购标题"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="采购需求详细描述"
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True, comment="采购品类"
    )
    quantity: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="采购数量"
    )
    unit: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="单位，如 件/箱/kg"
    )
    budget: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="预算金额"
    )
    budget_min: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="预算最低金额"
    )
    budget_max: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="预算最高金额"
    )
    deadline: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="截止日期（ISO 8601 字符串）"
    )

    # ---- 状态 ----
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True,
        comment="状态：pending/matched/completed/cancelled"
    )

    # ---- 时间戳 ----
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
        comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<Procurement(id={self.id}, title='{self.title}')>"
