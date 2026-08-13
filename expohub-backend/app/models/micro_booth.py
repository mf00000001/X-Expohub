"""
V2.0: 微展位（Micro Booth）
- 给犹豫展商免费试用，看到数据后升级买线下展位
- free: 1-3 个展品, regular: 1-8, flagship: 不限
- 统计：浏览量、搜索曝光量、被收藏数
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MicroBooth(Base):
    """微展位表"""
    __tablename__ = "micro_booths"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exhibitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="展商用户ID"
    )
    # V3.4: 所属展会(微展位分类到展会)
    exhibition_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=True, index=True, comment="所属展会ID"
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="微展位名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="简介"
    )
    logo_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="logo图片URL"
    )
    industry_domain: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True, comment="行业领域"
    )
    membership_tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free", index=True,
        comment="会员等级：free/regular/flagship"
    )

    # ---- 统计数据 ----
    view_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="浏览量"
    )
    search_appearances: Mapped[int] = mapped_column(
        Integer, default=0, comment="搜索曝光量"
    )
    favorite_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="被收藏数"
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", comment="状态：active/inactive"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<MicroBooth(id={self.id}, name='{self.name}', tier='{self.membership_tier}')>"
