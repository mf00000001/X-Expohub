"""
AI 原生层数据模型（P5 新增）

- AiUsageLog 用量账本：只记元数据（字符数/费用/渠道/能力），**不落库原始 prompt**
  （配合发送前 PII 脱敏，双重隐私护栏）
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AiUsageLog(Base):
    """AI 用量日志表"""
    __tablename__ = "ai_usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    capability: Mapped[str] = mapped_column(String(32), default="generic")
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    # 是否降级（真实渠道失败→mock）
    degraded: Mapped[int] = mapped_column(Integer, default=1)
    prompt_chars: Mapped[int] = mapped_column(Integer, default=0)
    response_chars: Mapped[int] = mapped_column(Integer, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=_utcnow)
