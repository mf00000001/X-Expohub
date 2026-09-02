"""
票务路由（P3 新增，前缀 /api/ticketing）

- 票种管理:   POST /ticket-types（主办方/管理员）
              GET /exhibitions/{id}/ticket-types（公开）
- 购票订单:   POST /orders（免费票直通 paid；付费票 pending）
              POST /orders/{order_no}/pay（Mock 支付）
              POST /orders/{order_no}/cancel（退单，名额回退）
              GET /orders/me
- 入场券:     GET /tickets/me（含签名二维码载荷）
              GET /tickets/{ticket_no}（核销前验签/验真）

金额单位：分。名额扣减用条件 UPDATE 保证原子性（SQLite 单写安全）。
"""
import hmac
import hashlib
import json
import random
import string
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_active_user, require_permission
from app.core.exceptions import BadRequest, Forbidden, NotFound
from app.core.permissions import Permission
from app.models.base import get_db
from app.models.exhibition import Exhibition
from app.models.user import User
from app.modules.ticketing.models import TicketType, TicketingOrder, Ticket
from app.modules.ticketing.pay import get_pay_provider

router = APIRouter(prefix="/ticketing", tags=["票务"])

ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_PAID = "paid"
ORDER_STATUS_CANCELLED = "cancelled"
TICKET_STATUS_VALID = "valid"


def _order_no() -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return "O" + ts + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _ticket_no() -> str:
    return "T" + "".join(random.choices(string.digits, k=14))


def _sign(ticket_no: str) -> str:
    """二维码签名：HMAC-SHA256(SECRET_KEY, ticket_no) 前 16 位"""
    return hmac.new(settings.SECRET_KEY.encode(), ticket_no.encode(), hashlib.sha256).hexdigest()[:16]


def _verify_sign(ticket_no: str, sig: str) -> bool:
    return hmac.compare_digest(_sign(ticket_no), sig or "")


def _qr_payload(ticket_no: str) -> str:
    return json.dumps({"t": ticket_no, "s": _sign(ticket_no)})


# ============================================================
# Schemas
# ============================================================

class TicketTypeCreate(BaseModel):
    exhibition_id: int
    name: str = Field(..., min_length=1, max_length=100)
    price_cents: int = Field(0, ge=0)
    quota: int = Field(1, ge=1)
    description: Optional[str] = None


class OrderCreate(BaseModel):
    exhibition_id: int
    ticket_type_id: int


class PayRequest(BaseModel):
    method: str = "mock"


# ============================================================
# 票种管理
# ============================================================

@router.post("/ticket-types")
def create_ticket_type(
    data: TicketTypeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.TICKET_MANAGE)),
):
    """主办方/管理员创建票种"""
    if not db.query(Exhibition).filter(Exhibition.id == data.exhibition_id).first():
        raise NotFound(message="展会不存在")
    tt = TicketType(
        exhibition_id=data.exhibition_id,
        name=data.name,
        price_cents=data.price_cents,
        quota=data.quota,
        description=data.description,
    )
    db.add(tt)
    db.commit()
    db.refresh(tt)
    return {"success": True, "code": "OK", "message": "票种创建成功", "data": {
        "id": tt.id, "exhibition_id": tt.exhibition_id, "name": tt.name,
        "price_cents": tt.price_cents, "quota": tt.quota, "active": tt.active,
    }}


@router.get("/exhibitions/{exhibition_id}/ticket-types")
def list_ticket_types(exhibition_id: int, db: Session = Depends(get_db)):
    """公开：某展会的在售票种列表"""
    items = db.query(TicketType).filter(
        TicketType.exhibition_id == exhibition_id, TicketType.active.is_(True)
    ).all()
    return {"success": True, "code": "OK", "message": "获取成功", "data": {
        "list": [
            {"id": t.id, "name": t.name, "price_cents": t.price_cents,
             "quota": t.quota, "description": t.description}
            for t in items
        ]
    }}


# ============================================================
# 下单 / 支付 / 取消
# ============================================================

@router.post("/orders")
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """创建订单：免费票直通 paid 并出票；付费票生成 pending（名额锁定）"""
    tt = db.query(TicketType).filter(
        TicketType.id == data.ticket_type_id,
        TicketType.exhibition_id == data.exhibition_id,
        TicketType.active.is_(True),
    ).first()
    if not tt:
        raise NotFound(message="票种不存在或已下架")
    if not db.query(Exhibition).filter(Exhibition.id == data.exhibition_id).first():
        raise NotFound(message="展会不存在")

    order = TicketingOrder(
        order_no=_order_no(),
        exhibition_id=data.exhibition_id,
        ticket_type_id=tt.id,
        ticket_type_name=tt.name,
        user_id=user.id,
        amount_cents=tt.price_cents,
        status=ORDER_STATUS_PENDING,
    )
    # 原子扣名额（含免费票名额；条件 UPDATE 防超卖）
    from sqlalchemy import update
    res = db.execute(
        update(TicketType).where(TicketType.id == tt.id, TicketType.quota > 0)
        .values(quota=TicketType.quota - 1)
    )
    if res.rowcount == 0:
        raise BadRequest(message="该票种已售罄")
    db.add(order)
    db.flush()

    # 免费票直通
    if tt.price_cents == 0:
        order.status = ORDER_STATUS_PAID
        order.pay_method = "free"
        order.paid_at = datetime.now(timezone.utc)
        _issue_ticket(db, order)

    db.commit()
    return {"success": True, "code": "OK", "message": "下单成功", "data": _order_view(order)}


@router.post("/orders/{order_no}/pay")
def pay_order(
    order_no: str,
    data: PayRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """发起支付（Mock 渠道发起即成功并出票）"""
    order = db.query(TicketingOrder).filter(TicketingOrder.order_no == order_no).first()
    if not order or order.user_id != user.id:
        raise NotFound(message="订单不存在")
    if order.status != ORDER_STATUS_PENDING:
        raise BadRequest(message=f"订单状态不允许支付：{order.status}")

    provider = get_pay_provider(data.method)
    if not provider:
        raise BadRequest(message=f"不支持的支付方式: {data.method}")

    pay_result = provider.create_payment(order.order_no, order.amount_cents, order.ticket_type_name)
    if pay_result.get("paid"):
        order.status = ORDER_STATUS_PAID
        order.pay_method = data.method
        order.paid_at = datetime.now(timezone.utc)
        ticket = _issue_ticket(db, order)
        db.commit()
        return {"success": True, "code": "OK", "message": "支付成功", "data": {
            "order": _order_view(order),
            "ticket_no": ticket.ticket_no,
        }}
    raise BadRequest(message="支付未完成")  # 真实渠道走回调，此处不出现


@router.post("/orders/{order_no}/cancel")
def cancel_order(
    order_no: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """取消订单（pending 才可取消；名额回退）"""
    order = db.query(TicketingOrder).filter(TicketingOrder.order_no == order_no).first()
    if not order or order.user_id != user.id:
        raise NotFound(message="订单不存在")
    if order.status != ORDER_STATUS_PENDING:
        raise BadRequest(message="仅待支付订单可取消")

    from sqlalchemy import update
    db.execute(
        update(TicketType).where(TicketType.id == order.ticket_type_id)
        .values(quota=TicketType.quota + 1)
    )
    order.status = ORDER_STATUS_CANCELLED
    order.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "code": "OK", "message": "订单已取消，名额已释放", "data": _order_view(order)}


@router.get("/orders/me")
def my_orders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """我的订单"""
    items = db.query(TicketingOrder).filter(TicketingOrder.user_id == user.id) \
        .order_by(TicketingOrder.id.desc()).limit(100).all()
    return {"success": True, "code": "OK", "message": "获取成功", "data": {
        "list": [_order_view(o) for o in items]
    }}


# ============================================================
# 入场券
# ============================================================

@router.get("/tickets/me")
def my_tickets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """我的有效入场券（含签名二维码载荷）"""
    items = db.query(Ticket).filter(
        Ticket.user_id == user.id, Ticket.status == TICKET_STATUS_VALID
    ).order_by(Ticket.id.desc()).all()
    return {"success": True, "code": "OK", "message": "获取成功", "data": {
        "list": [
            {"ticket_no": t.ticket_no, "exhibition_id": t.exhibition_id,
             "ticket_type_name": t.ticket_type_name, "qr_payload": t.qr_payload}
            for t in items
        ]
    }}


@router.get("/tickets/{ticket_no}/verify")
def verify_ticket(
    ticket_no: str,
    signature: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """验票：校验签名与状态（现场核销用；签名可来自 qr_payload 的 s 字段）"""
    t = db.query(Ticket).filter(Ticket.ticket_no == ticket_no).first()
    if not t:
        raise NotFound(message="票券不存在")
    if signature and not _verify_sign(ticket_no, signature):
        raise BadRequest(message="票券签名校验失败")
    return {"success": True, "code": "OK", "message": "校验通过" if t.status == TICKET_STATUS_VALID else "非有效状态", "data": {
        "ticket_no": t.ticket_no,
        "exhibition_id": t.exhibition_id,
        "ticket_type_name": t.ticket_type_name,
        "status": t.status,
        "valid": t.status == TICKET_STATUS_VALID,
    }}


# ============================================================
# helpers
# ============================================================

def _issue_ticket(db: Session, order: TicketingOrder) -> Ticket:
    """出票（订单须为 paid）"""
    ticket_no = _ticket_no()
    ticket = Ticket(
        ticket_no=ticket_no,
        order_no=order.order_no,
        exhibition_id=order.exhibition_id,
        ticket_type_name=order.ticket_type_name,
        user_id=order.user_id,
        qr_payload=_qr_payload(ticket_no),
        status=TICKET_STATUS_VALID,
    )
    db.add(ticket)
    return ticket


def _order_view(o: TicketingOrder) -> dict:
    return {
        "order_no": o.order_no,
        "exhibition_id": o.exhibition_id,
        "ticket_type_name": o.ticket_type_name,
        "amount_cents": o.amount_cents,
        "status": o.status,
        "pay_method": o.pay_method,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
    }
