"""
平台运营域数据模型（P6 新增）

- TenantPlan         计费档位注册表（basic/standard/pro；按功能解锁、不限场次）
- TenantSubscription 租户当前订阅（默认回落 basic）
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantPlan(Base):
    """计费档位表"""
    __tablename__ = "tenant_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 档位标识: basic / standard / pro
    tier: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    monthly_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    # 功能点列表（JSON 字符串，如 ["ticketing","ai","onsite"]）
    features_json: Mapped[str] = mapped_column(Text, default="[]")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class TenantSubscription(Base):
    """租户订阅表（tenant_id 目前缺省为 default 单租户；多租户启用后逐租户记录）"""
    __tablename__ = "tenant_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, default="default")
    plan_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
