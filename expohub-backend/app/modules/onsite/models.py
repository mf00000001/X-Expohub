"""
现场签到域数据模型（P4 新增）

- OnsiteCheckinLog 核销流水：一次核销/撤销一条记录（append-only），
  供撤销审计、到场统计、热力/时段曲线使用。
入场券状态迁移（tickets.status）：valid -> used(核销) -> valid(撤销)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OnsiteCheckinLog(Base):
    """现场核销流水表"""
    __tablename__ = "onsite_checkin_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exhibition_id: Mapped[int] = mapped_column(Integer, index=True, comment="展会 id")
    ticket_no: Mapped[str] = mapped_column(String(40), index=True, comment="入场券号")
    ticket_type_name: Mapped[str] = mapped_column(String(100), default="", comment="票种名快照")
    user_id: Mapped[int] = mapped_column(Integer, index=True, comment="持票人")
    operator_id: Mapped[int] = mapped_column(Integer, index=True, comment="核销操作人")
    # action: checkin(入场) / revoke(撤销)
    action: Mapped[str] = mapped_column(String(16), default="checkin", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=_utcnow)
