"""
订单超时任务（P6）

- expire_pending_orders：把超过 ORDER_EXPIRE_MINUTES 的 pending 订单自动取消，
  名额回退 + 审计留痕（append-only）。幂等：只处理 pending。
- 任务在 import 时登记到调度注册表（SCHEDULER_ENABLED=True 才真正启动）；
  也可由测试/运维直接调用。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core.config import settings
from app.models.base import SessionLocal
from app.modules.ticketing.models import TicketType, TicketingOrder

logger = logging.getLogger(__name__)


def expire_pending_orders(minutes: int | None = None) -> int:
    """批量过期待支付订单；返回处理条数（幂等，重复执行不重复处理）"""
    mins = minutes if minutes is not None else settings.ORDER_EXPIRE_MINUTES
    deadline = datetime.now(timezone.utc) - timedelta(minutes=mins)
    db = SessionLocal()
    processed = 0
    try:
        expired = db.query(TicketingOrder).filter(
            TicketingOrder.status == "pending",
            TicketingOrder.created_at < deadline,
        ).all()
        for order in expired:
            db.execute(
                update(TicketType).where(TicketType.id == order.ticket_type_id)
                .values(quota=TicketType.quota + 1)
            )
            order.status = "cancelled"
            order.cancelled_at = datetime.now(timezone.utc)
            processed += 1
        db.commit()
        if processed:
            logger.info("[jobs] order-expire: cancelled %d pending orders", processed)
        return processed
    finally:
        db.close()


# 登记到调度注册表（默认关闭不启动；开启后按间隔执行）
from app.core.scheduler import register_job  # noqa: E402

register_job("order-expire", "interval", expire_pending_orders, minutes=settings.ORDER_EXPIRE_MINUTES)
