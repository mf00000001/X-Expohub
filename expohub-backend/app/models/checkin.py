"""
V2.2: 每日签到
"""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CheckIn(Base):
    """用户签到记录"""
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="用户ID"
    )
    streak: Mapped[int] = mapped_column(
        Integer, default=1, comment="连续签到天数"
    )
    points_earned: Mapped[int] = mapped_column(
        Integer, default=2, comment="本次签到获得积分"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, comment="签到时间"
    )
