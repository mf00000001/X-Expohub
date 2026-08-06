"""
采购需求匹配表（ProcurementMatch）

展商对采购需求提交的匹配/投标记录
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Text, Integer, Float, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProcurementMatch(Base):
    """采购匹配表 — 展商对采购需求提交的投标"""
    __tablename__ = "procurement_matches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 关联 ----
    procurement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("procurements.id"), nullable=False, index=True,
        comment="关联采购需求 ID"
    )
    exhibitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="展商用户 ID"
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=True, index=True,
        comment="关联展品 ID"
    )

    # ---- 投标信息 ----
    message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展商留言/投标说明"
    )
    quoted_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="报价金额"
    )

    # ---- 状态 ----
    is_accepted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="是否已被采购方接受"
    )

    # ---- 时间戳 ----
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="投标时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
        comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<ProcurementMatch(id={self.id}, procurement_id={self.procurement_id})>"
