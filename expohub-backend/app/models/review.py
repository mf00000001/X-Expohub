"""
评价表（Review）

对应前端 API: expo-hub-uniapp/src/api/review.ts

前端 Review 接口字段：
  id, exhibition_id?, booth_id?, reviewer_id, reviewer_name?,
  target_type, target_id, rating, content, created_at

支持多态评价目标：exhibition / booth / product
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Review(Base):
    """评价表 — 支持对展会/展位/展品的多态评价"""
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 关联（可空外键应对多态） ----
    exhibition_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=True, index=True,
        comment="被评价展会 ID"
    )
    booth_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("booths.id"), nullable=True, index=True,
        comment="被评价展位 ID"
    )

    # ---- 评价人 ----
    reviewer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="评价人用户 ID"
    )
    reviewer_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="评价人名称（冗余）"
    )

    # ---- 多态目标 ----
    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="评价目标类型：exhibition/booth/product"
    )
    target_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True,
        comment="评价目标 ID"
    )

    # ---- 评价内容 ----
    rating: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="评分（1-5 星）"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="评价内容"
    )

    # ---- 时间戳 ----
    created_at: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="评价时间（ISO 8601 字符串）"
    )

    def __repr__(self) -> str:
        return f"<Review(id={self.id}, target={self.target_type}:{self.target_id}, rating={self.rating})>"
