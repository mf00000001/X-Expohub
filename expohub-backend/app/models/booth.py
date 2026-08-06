"""
展位表（Booth）

对应前端 API: expo-hub-uniapp/src/api/booth.ts

前端 Booth 接口字段：
  id, exhibition_id, booth_number, exhibitor_id?, exhibitor_name?,
  company_name?, size?, location_area?, price?, status,
  description?, created_at?, updated_at?
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Booth(Base):
    """展位表"""
    __tablename__ = "booths"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 关联 ----
    exhibition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=False, index=True,
        comment="所属展会 ID"
    )
    exhibitor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
        comment="展商用户 ID（空表示未分配）"
    )

    # ---- 展位标识 ----
    booth_number: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="展位编号，如 A-001"
    )

    # ---- 冗余展示信息（与前端 Booth 接口对齐） ----
    exhibitor_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="展商名称（冗余）"
    )
    company_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="公司名称（冗余）"
    )

    # ---- 展位属性（与前端接口对齐） ----
    size: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="展位尺寸，如 3x3m"
    )
    location_area: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="展区位置，如 A区/主厅"
    )
    price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="展位价格"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展位描述"
    )

    # ---- 状态 ----
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="available", index=True,
        comment="状态：available/reserved/occupied/maintenance"
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
        return f"<Booth(id={self.id}, number='{self.booth_number}')>"
