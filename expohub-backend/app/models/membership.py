"""
V2.0: 会员体系
- free: 免费，可挂 1-3 个展品
- regular: 普通会员，可挂 1-8 个展品
- flagship: 旗舰会员，不限展品数量
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Membership(Base):
    """展商会员订阅表"""
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="展商用户ID"
    )
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free", index=True,
        comment="会员等级：free/regular/flagship"
    )
    product_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3,
        comment="展品数量上限（free=3, regular=8, flagship=0表示无限）"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, comment="开始时间"
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="过期时间（free永久）"
    )
    auto_renew: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否自动续费"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, comment="创建时间"
    )

    def __repr__(self) -> str:
        return f"<Membership(id={self.id}, user={self.user_id}, tier='{self.tier}')>"


# 各等级展品上限
TIER_PRODUCT_LIMITS = {
    "free": 3,
    "regular": 8,
    "flagship": 50,  # 旗舰最多展示50件
}
