"""
展会表（Exhibition）

对应前端 API: expo-hub-uniapp/src/api/exhibition.ts

前端 Exhibition 接口字段：
  id, title, description, cover_image?, start_date, end_date,
  location, status, organizer_id?, organizer_name?,
  created_at?, updated_at?
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Exhibition(Base):
    """展会信息表"""
    __tablename__ = "exhibitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 基本信息（与前端 Exhibition 接口对齐） ----
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True, comment="展会标题"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展会描述"
    )
    title_en: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="展会标题（英文）"
    )
    description_en: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展会描述（英文）"
    )
    cover_image: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="封面图 URL"
    )

    # ---- 时间 ----
    start_date: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="开始时间（ISO 8601 字符串）"
    )
    end_date: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="结束时间（ISO 8601 字符串）"
    )

    # ---- 地点（前端用单一 location 字段） ----
    location: Mapped[str] = mapped_column(
        String(300), nullable=False, comment="举办地点"
    )

    # ---- V2.0: 首页引流字段 ----
    is_featured: Mapped[bool] = mapped_column(
        default=False, comment="是否精选展会（用于首页重磅推荐）"
    )
    hot_score: Mapped[int] = mapped_column(
        Integer, default=0, comment="热度分数（浏览量+报名数加权）"
    )
    visitor_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="预计/实际参观人数"
    )

    # ---- 状态与主办方 ----
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True,
        comment="状态：draft/pending/published/ongoing/ended/cancelled"
    )
    organizer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
        comment="主办方用户 ID"
    )
    organizer_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="主办方名称（冗余）"
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
        return f"<Exhibition(id={self.id}, title='{self.title}')>"
