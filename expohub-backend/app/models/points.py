"""
V2.2: 商业积分系统
积分规则 + 账本 + 兑换目录
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PointsLedger(Base):
    """积分账本（复式记账）"""
    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID"
    )
    transaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True,
        comment="交易类型：earn_browse/earn_procurement/earn_booking/earn_registration/redeem_vip/redeem_lunch/redeem_gift"
    )
    amount: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="积分变动（正=收入，负=支出）"
    )
    balance_after: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="交易后余额"
    )
    reference_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="关联实体类型"
    )
    reference_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="关联实体ID"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="说明"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, comment="交易时间"
    )


# ============================================================
# 积分规则（内存配置，可迁移到DB）
# ============================================================

POINTS_RULES = {
    "earn_browse":       {"amount": 1,  "daily_cap": 10,  "label": "浏览展商"},
    "earn_procurement":  {"amount": 5,  "daily_cap": 25,  "label": "提交采购需求"},
    "earn_booking":      {"amount": 10, "daily_cap": 30,  "label": "预约展位"},
    "earn_registration": {"amount": 15, "daily_cap": 30,  "label": "报名展会"},
}

REDEEM_CATALOG = [
    {"id": 1, "name": "VIP快速通道", "points": 100, "stock": "limited", "icon": "🌟"},
    {"id": 2, "name": "商务午餐券",  "points": 50,  "stock": "unlimited", "icon": "🍽️"},
    {"id": 3, "name": "展会纪念品",  "points": 30,  "stock": "unlimited", "icon": "🎁"},
]
