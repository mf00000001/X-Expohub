"""
票务域数据模型（P3 新增）

- TicketType    票种（展会维度：名称/价格/名额）
- TicketingOrder 订单（免费票直通 paid；付费票 pending→pay）
- Ticket        入场券（唯一 ticket_no + 签名二维码载荷）

金额一律以“分”存储（整数），避免浮点误差。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TicketType(Base):
    """票种表"""
    __tablename__ = "ticket_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exhibition_id: Mapped[int] = mapped_column(Integer, index=True, comment="展会 id")
    name: Mapped[str] = mapped_column(String(100), comment="票种名称，如 早鸟票/普通票")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # 价格（分）：0 = 免费票
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    # 名额：剩余可售数量（下单即扣减，取消/超时回退）
    quota: Mapped[int] = mapped_column(Integer, default=0)
    # 是否仍在售卖（主办方可下架）
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class TicketingOrder(Base):
    """票务订单表"""
    __tablename__ = "ticketing_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    exhibition_id: Mapped[int] = mapped_column(Integer, index=True)
    ticket_type_id: Mapped[int] = mapped_column(Integer)
    ticket_type_name: Mapped[str] = mapped_column(String(100), default="")
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    # 金额快照（分）
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    # 状态机: pending -> paid / cancelled ; paid -> refunded
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    pay_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Ticket(Base):
    """入场券表"""
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    order_no: Mapped[str] = mapped_column(String(40), index=True)
    exhibition_id: Mapped[int] = mapped_column(Integer, index=True)
    ticket_type_name: Mapped[str] = mapped_column(String(100), default="")
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    # 二维码载荷（含签名，核销时验签）
    qr_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 状态: valid / used / refunded
    status: Mapped[str] = mapped_column(String(20), default="valid", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
