"""P3 票务域端到端 API 测试（隔离测试库，不碰开发数据）

设计原则：各测试自包含、与执行顺序解耦——
- 票种/验票样本由 fixture 直接落库；
- 名额防超卖测试用「自己的限额票种」，不依赖跨用例配额推算。

运行: cd expohub-backend && python -m pytest tests/test_ticketing_api.py -v
"""
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.base import SessionLocal
from app.models.exhibition import Exhibition
from app.models.user import User
from app.modules.ticketing.models import TicketType, TicketingOrder, Ticket
from app.modules.ticketing.routes import _sign, _qr_payload


def _seed_user(db, username: str, role: str) -> User:
    u = User(
        username=username,
        email=f"{username}@test.local",
        password_hash=hash_password("testpass123"),
        role=role,
        status="active",
        is_onboarded=True,
        total_points=0,
        token_version=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _seed_exhibition(db) -> Exhibition:
    e = Exhibition(
        title="票务测试展",
        start_date="2026-10-01T09:00:00",
        end_date="2026-10-03T18:00:00",
        location="上海国家会展中心",
        status="registering",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id, 'role': user.role, 'ver': 0})}"}


@pytest.fixture(scope="module")
def ctx():
    with TestClient(app) as client:
        db = SessionLocal()
        org = _seed_user(db, "org_ticket", "organizer")
        buyer = _seed_user(db, "buyer_ticket", "buyer")
        visitor = _seed_user(db, "visitor_ticket", "visitor")
        payer = _seed_user(db, "payer_ticket", "buyer")
        expo = _seed_exhibition(db)
        free_tt = TicketType(exhibition_id=expo.id, name="免费票", price_cents=0, quota=100)
        paid_tt = TicketType(exhibition_id=expo.id, name="普通票", price_cents=9900, quota=10)
        db.add_all([free_tt, paid_tt])
        db.commit()
        # 验票样本：直接落一张已支付的普通票（含签名二维码载荷）
        verify_order = TicketingOrder(
            order_no="OVERIFY00000001", exhibition_id=expo.id, ticket_type_id=paid_tt.id,
            ticket_type_name="普通票", user_id=visitor.id, amount_cents=9900,
            status="paid", pay_method="mock", paid_at=datetime.now(timezone.utc),
        )
        verify_ticket = Ticket(
            ticket_no="TVERIFY0000000001", order_no="OVERIFY00000001", exhibition_id=expo.id,
            ticket_type_name="普通票", user_id=visitor.id, qr_payload=_qr_payload("TVERIFY0000000001"),
        )
        db.add_all([verify_order, verify_ticket])
        db.commit()
        # 最后一次 commit 过期所有属性：refresh 后在同一会话内取标量并生成令牌
        db.refresh(org); db.refresh(buyer); db.refresh(visitor); db.refresh(payer)
        db.refresh(expo); db.refresh(free_tt); db.refresh(paid_tt)
        expo_id, free_tt_id, paid_tt_id = expo.id, free_tt.id, paid_tt.id
        org_h, buyer_h, visitor_h, payer_h = _auth(org), _auth(buyer), _auth(visitor), _auth(payer)
        db.close()
        yield {
            "client": client, "expo_id": expo_id, "free_tt_id": free_tt_id, "paid_tt_id": paid_tt_id,
            "org": org_h, "buyer": buyer_h, "visitor": visitor_h, "payer": payer_h,
            "verify_ticket_no": "TVERIFY0000000001", "verify_sign": _sign("TVERIFY0000000001"),
        }


class TestTicketType:
    def test_organizer_creates_additional_ticket_type(self, ctx):
        r = ctx["client"].post("/api/ticketing/ticket-types", json={
            "exhibition_id": ctx["expo_id"], "name": "VIP票", "price_cents": 29900, "quota": 5,
        }, headers=ctx["org"])
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "VIP票"

    def test_visitor_cannot_create(self, ctx):
        r = ctx["client"].post("/api/ticketing/ticket-types", json={
            "exhibition_id": ctx["expo_id"], "name": "x", "price_cents": 1, "quota": 1,
        }, headers=ctx["visitor"])
        assert r.status_code in (403, 401)

    def test_public_list(self, ctx):
        r = ctx["client"].get(f"/api/ticketing/exhibitions/{ctx['expo_id']}/ticket-types")
        assert r.status_code == 200
        names = {x["name"] for x in r.json()["data"]["list"]}
        assert {"免费票", "普通票"} <= names


class TestOrders:
    def test_free_ticket_instant_paid(self, ctx):
        r = ctx["client"].post("/api/ticketing/orders", json={
            "exhibition_id": ctx["expo_id"], "ticket_type_id": ctx["free_tt_id"],
        }, headers=ctx["buyer"])
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["status"] == "paid" and d["amount_cents"] == 0

    def test_paid_ticket_pending_then_mock_pay(self, ctx):
        # payer 独立账户：支付前无票，支付后恰 1 张（与验票样本账户隔离）
        r = ctx["client"].post("/api/ticketing/orders", json={
            "exhibition_id": ctx["expo_id"], "ticket_type_id": ctx["paid_tt_id"],
        }, headers=ctx["payer"])
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["status"] == "pending" and d["amount_cents"] == 9900
        order_no = d["order_no"]

        before = ctx["client"].get("/api/ticketing/tickets/me", headers=ctx["payer"]).json()["data"]["list"]
        assert before == []

        r = ctx["client"].post(f"/api/ticketing/orders/{order_no}/pay", json={"method": "mock"}, headers=ctx["payer"])
        assert r.status_code == 200
        assert r.json()["data"]["order"]["status"] == "paid"
        assert r.json()["data"]["ticket_no"].startswith("T")

        after = ctx["client"].get("/api/ticketing/tickets/me", headers=ctx["payer"]).json()["data"]["list"]
        assert len(after) == 1 and after[0]["ticket_no"].startswith("T")

    def test_quota_exhaustion_self_contained(self, ctx):
        # 自建 限额票 quota=2：两个订单占满 → 第三单售罄 400 → 取消一单 → 名额回退可再下单
        r = ctx["client"].post("/api/ticketing/ticket-types", json={
            "exhibition_id": ctx["expo_id"], "name": "限额票", "price_cents": 5000, "quota": 2,
        }, headers=ctx["org"])
        tt_id = r.json()["data"]["id"]

        o1 = ctx["client"].post("/api/ticketing/orders", json={
            "exhibition_id": ctx["expo_id"], "ticket_type_id": tt_id,
        }, headers=ctx["buyer"])
        o2 = ctx["client"].post("/api/ticketing/orders", json={
            "exhibition_id": ctx["expo_id"], "ticket_type_id": tt_id,
        }, headers=ctx["buyer"])
        assert o1.status_code == 200 and o2.status_code == 200

        o3 = ctx["client"].post("/api/ticketing/orders", json={
            "exhibition_id": ctx["expo_id"], "ticket_type_id": tt_id,
        }, headers=ctx["buyer"])
        assert o3.status_code == 400  # 售罄

        cancel_no = o2.json()["data"]["order_no"]
        rc = ctx["client"].post(f"/api/ticketing/orders/{cancel_no}/cancel", headers=ctx["buyer"])
        assert rc.status_code == 200 and rc.json()["data"]["status"] == "cancelled"

        again = ctx["client"].post("/api/ticketing/orders", json={
            "exhibition_id": ctx["expo_id"], "ticket_type_id": tt_id,
        }, headers=ctx["buyer"])
        assert again.status_code == 200  # 名额已释放

    def test_my_orders_and_tickets(self, ctx):
        orders = ctx["client"].get("/api/ticketing/orders/me", headers=ctx["buyer"]).json()["data"]["list"]
        assert len(orders) >= 1
        tickets = ctx["client"].get("/api/ticketing/tickets/me", headers=ctx["buyer"]).json()["data"]["list"]
        # buyer 至少有免费票；qr_payload 必须含签名
        assert len(tickets) >= 1
        for t in tickets:
            payload = json.loads(t["qr_payload"])
            assert "t" in payload and "s" in payload


class TestVerifyTicket:
    def test_verify_valid_ticket(self, ctx):
        r = ctx["client"].get(
            f"/api/ticketing/tickets/{ctx['verify_ticket_no']}/verify",
            params={"signature": ctx["verify_sign"]},
        )
        assert r.status_code == 200
        assert r.json()["data"]["valid"] is True

    def test_verify_bad_signature_rejected(self, ctx):
        r = ctx["client"].get(
            f"/api/ticketing/tickets/{ctx['verify_ticket_no']}/verify",
            params={"signature": "deadbeef"},
        )
        assert r.status_code == 400

    def test_verify_unknown_ticket_404(self, ctx):
        r = ctx["client"].get("/api/ticketing/tickets/T99999999999999/verify")
        assert r.status_code == 404
