"""P4 现场签到域端到端 API 测试（隔离测试库）

覆盖:
1. 主办方核销有效票 → 200，票转 used，流水落库
2. 重复核销 → 400
3. 错误签名 / 他人展会票 → 400
4. 批量核销：成功 + 重复项跳过（幂等）
5. 撤销核销 → 票恢复 valid
6. 统计：总数/票种分布/小时曲线/最新流水
7. 游客无权限 → 403

运行: cd expohub-backend && python -m pytest tests/test_onsite_api.py -v
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.base import SessionLocal
from app.models.exhibition import Exhibition
from app.models.user import User
from app.modules.ticketing.models import Ticket
from app.modules.ticketing.routes import _qr_payload


def _seed_user(db, username: str, role: str) -> User:
    u = User(
        username=username, email=f"{username}@test.local",
        password_hash=hash_password("x"), role=role, status="active",
        is_onboarded=True, total_points=0, token_version=0,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _seed_exhibition(db) -> Exhibition:
    e = Exhibition(title="现场测试展", start_date="2026-10-01T09:00:00",
                   end_date="2026-10-03T18:00:00", location="广州琶洲", status="live")
    db.add(e); db.commit(); db.refresh(e)
    return e


def _seed_ticket(db, ticket_no: str, exhibition_id: int, user_id: int, status="valid") -> Ticket:
    t = Ticket(
        ticket_no=ticket_no, order_no=f"O-{ticket_no}", exhibition_id=exhibition_id,
        ticket_type_name="普通票", user_id=user_id, qr_payload=_qr_payload(ticket_no), status=status,
    )
    db.add(t); db.commit(); db.refresh(t)
    return t


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id, 'role': user.role, 'ver': 0})}"}


@pytest.fixture(scope="module")
def ctx():
    with TestClient(app) as client:
        db = SessionLocal()
        org = _seed_user(db, "org_onsite", "organizer")
        attendee = _seed_user(db, "attendee_onsite", "visitor")
        visitor = _seed_user(db, "noperm_onsite", "visitor")
        expo = _seed_exhibition(db)
        expo2 = _seed_exhibition(db)
        t_a = _seed_ticket(db, "TONSITE0000000001", expo.id, attendee.id)
        t_b = _seed_ticket(db, "TONSITE0000000002", expo.id, attendee.id)
        t_c = _seed_ticket(db, "TONSITE0000000003", expo2.id, attendee.id)  # 其他展会票
        # 最终 commit 已过期先前实例：统一 refresh 后取标量并生成令牌
        for obj in (org, attendee, visitor, expo, t_a, t_b, t_c):
            db.refresh(obj)
        org_h = _auth(org); attendee_h = _auth(attendee); visitor_h = _auth(visitor)
        expo_id, other_expo_id = expo.id, expo2.id
        t1, t2, t3 = t_a.ticket_no, t_b.ticket_no, t_c.ticket_no
        db.close()
        yield {"client": client, "expo_id": expo_id, "other_expo_id": other_expo_id,
               "org": org_h, "attendee": attendee_h, "visitor": visitor_h,
               "t1": t1, "t2": t2, "t3": t3}


class TestCheckin:
    def test_single_checkin_success(self, ctx):
        import json
        signature = json.loads(_qr_payload(ctx["t1"]))["s"]
        r = ctx["client"].post("/api/onsite/checkin", json={
            "exhibition_id": ctx["expo_id"], "ticket_no": ctx["t1"], "signature": signature,
        }, headers=ctx["org"])
        assert r.status_code == 200
        assert r.json()["data"]["ok"] is True

    def test_duplicate_checkin_rejected(self, ctx):
        import json
        signature = json.loads(_qr_payload(ctx["t1"]))["s"]
        r = ctx["client"].post("/api/onsite/checkin", json={
            "exhibition_id": ctx["expo_id"], "ticket_no": ctx["t1"], "signature": signature,
        }, headers=ctx["org"])
        assert r.status_code == 400  # 已核销

    def test_bad_signature_rejected(self, ctx):
        r = ctx["client"].post("/api/onsite/checkin", json={
            "exhibition_id": ctx["expo_id"], "ticket_no": ctx["t2"], "signature": "deadbeef00",
        }, headers=ctx["org"])
        assert r.status_code == 400

    def test_wrong_exhibition_ticket_rejected(self, ctx):
        import json
        signature = json.loads(_qr_payload(ctx["t3"]))["s"]
        r = ctx["client"].post("/api/onsite/checkin", json={
            "exhibition_id": ctx["expo_id"], "ticket_no": ctx["t3"], "signature": signature,
        }, headers=ctx["org"])
        assert r.status_code == 400  # 不属于本展会

    def test_visitor_no_permission(self, ctx):
        import json
        signature = json.loads(_qr_payload(ctx["t2"]))["s"]
        r = ctx["client"].post("/api/onsite/checkin", json={
            "exhibition_id": ctx["expo_id"], "ticket_no": ctx["t2"], "signature": signature,
        }, headers=ctx["visitor"])
        assert r.status_code in (401, 403)


class TestBatchAndRevoke:
    def test_batch_checkin_idempotent(self, ctx):
        import json
        items = [
            {"exhibition_id": ctx["expo_id"], "ticket_no": ctx["t2"], "signature": json.loads(_qr_payload(ctx["t2"]))["s"]},
            # 已核销的 t1 重复提交 → 跳过
            {"exhibition_id": ctx["expo_id"], "ticket_no": ctx["t1"], "signature": json.loads(_qr_payload(ctx["t1"]))["s"]},
            {"exhibition_id": ctx["expo_id"], "ticket_no": "TONSITE9999999999", "signature": "x" * 16},
        ]
        r = ctx["client"].post("/api/onsite/checkin/batch", json={
            "exhibition_id": ctx["expo_id"], "items": items,
        }, headers=ctx["org"])
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["success_count"] == 1 and d["total"] == 3
        by_no = {x["ticket_no"]: x for x in d["results"]}
        assert by_no[ctx["t1"]]["ok"] is False      # 已核销跳过
        assert by_no["TONSITE9999999999"]["ok"] is False

    def test_revoke_restores_ticket(self, ctx):
        r = ctx["client"].post(f"/api/onsite/tickets/{ctx['t2']}/revoke",
                               params={"exhibition_id": ctx["expo_id"]}, headers=ctx["org"])
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "valid"

        # 恢复后可再次核销
        import json
        signature = json.loads(_qr_payload(ctx["t2"]))["s"]
        r2 = ctx["client"].post("/api/onsite/checkin", json={
            "exhibition_id": ctx["expo_id"], "ticket_no": ctx["t2"], "signature": signature,
        }, headers=ctx["org"])
        assert r2.status_code == 200


class TestStats:
    def test_stats_after_events(self, ctx):
        r = ctx["client"].get(f"/api/onsite/exhibitions/{ctx['expo_id']}/stats", headers=ctx["org"])
        assert r.status_code == 200
        d = r.json()["data"]
        # t1 核销1次(未撤销) + t2 核销2次(1撤销1再核销) = 3 条 checkin、1 条 revoke
        assert d["checkin_count"] == 3
        assert d["revoke_count"] == 1
        assert d["by_ticket_type"].get("普通票", 0) == 3
        assert len(d["by_hour"]) >= 1
        assert len(d["latest"]) >= 1
