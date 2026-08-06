"""
V2.2: 埋点事件表
记录用户行为：浏览、搜索、收藏、预约
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AnalyticsEvent(Base):
    """用户行为埋点事件"""
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="事件类型：page_view/search_impression/favorite/booking/inquiry"
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="实体类型：exhibition/booth/product/micro_booth"
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="实体ID"
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="触发用户ID（匿名可为空）"
    )
    source_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="被浏览/收藏的展商用户ID"
    )
    extra_data: Mapped[Optional[str]] = mapped_column(
        "metadata_json", Text, nullable=True, comment="JSON附加信息（搜索关键词等）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True, comment="事件时间"
    )

    def __repr__(self) -> str:
        return f"<AnalyticsEvent({self.event_type} on {self.entity_type}#{self.entity_id})>"
