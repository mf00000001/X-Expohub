"""通用收藏表（Favorite）

V2.8 原为内存存储（user_favs 字典），本模型将其落库；
favorite_count 计数与收藏关系保持事务内一致。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Favorite(Base):
    """通用收藏表 — 用户收藏产品/微展位/展会"""
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_favorite_user_entity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 关联 ----
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="收藏用户 ID"
    )
    entity_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="收藏实体类型：product/micro_booth/exhibition"
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="收藏实体 ID"
    )

    # ---- 时间戳 ----
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="收藏时间"
    )

    def __repr__(self) -> str:
        return f"<Favorite(user={self.user_id}, {self.entity_type}:{self.entity_id})>"
