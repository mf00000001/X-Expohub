"""P6 平台运营域测试（隔离测试库）+ 订单过期任务

覆盖:
1. 档位：公开列表 / 管理员创建/更新 / 游客创建 403
2. 订阅：默认回落基础版；管理员分配后生效
3. 用量快照：me/plan 返回计数
4. 批量导入展会：成功/标题去重跳过/非法状态逐行失败
5. 平台总览（管理员）
6. order-expire 任务：过期 pending 自动取消 + 名额回退；重复执行幂等

运行: cd expohub-backend && python -m pytest tests/test_platform_api.py -v
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.base import SessionLocal
from app.models.exhibition import Exhibition
from app.models.user import User
from app.modules.platform.models import TenantPlan
from app.modules.ticketing.models import TicketType, TicketingOrder


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
    e = Exhibition(title="P6基础展会", start_date="2026-10-01T09:00:00",
                   end_date="2026-10-03T18:00:00", location="杭州国际博览中心", status="draft")
    db.add(e); db.commit(); db.refresh(e)
    return e


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id, 'role': user.role, 'ver': 0})}"}


@pytest.fixture(scope="module")
def ctx():
    with TestClient(app) as client:
        db = SessionLocal()
        admin = _seed_user(db, "admin_p6", "admin")
        org = _seed_user(db, "org_p6", "organizer")
        visitor = _seed_user(db, "visitor_p6", "visitor")
        _seed_exhibition(db)
        for obj in (admin, org, visitor):
            db.refresh(obj)
        admin_h, org_h, visitor_h = _auth(admin), _auth(org), _auth(visitor)
        db.close()
        yield {"client": client, "admin": admin_h, "org": org_h, "visitor": visitor_h}


class TestPlans:
    def test_list_plans_empty_default(self, ctx):
        r = ctx["client"].get("/api/platform/plans")
        assert r.status_code == 200
        assert r.json()["data"]["list"] == []

    def test_admin_creates_plan(self, ctx):
        r = ctx["client"].post("/api/platform/plans", json={
            "tier": "standard", "name": "标准版", "monthly_fee_cents": 9900,
            "features": ["ticketing", "onsite", "ai"],
        }, headers=ctx["admin"])
        assert r.status_code == 200
        assert r.json()["data"]["tier"] == "standard"
        ctx["standard_plan_id"] = r.json()["data"]["id"]

    def test_visitor_cannot_create_plan(self, ctx):
        r = ctx["client"].post("/api/platform/plans", json={
            "tier": "pro", "name": "专业版", "monthly_fee_cents": 29900, "features": [],
        }, headers=ctx["visitor"])
        assert r.status_code in (401, 403)


class TestSubscription:
    def test_default_plan_basic(self, ctx):
        r = ctx["client"].get("/api/platform/me/plan", headers=ctx["visitor"])
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["plan"]["tier"] == "basic"
        assert d["usage"]["exhibitions_count"] >= 1

    def test_admin_assigns_plan(self, ctx):
        r = ctx["client"].put("/api/platform/tenants/default/plan",
                              json={"plan_id": ctx["standard_plan_id"]}, headers=ctx["admin"])
        assert r.status_code == 200
        assert r.json()["data"]["plan"]["tier"] == "standard"
        r2 = ctx["client"].get("/api/platform/me/plan", headers=ctx["visitor"])
        assert r2.json()["data"]["plan"]["tier"] == "standard"


class TestImportExhibitions:
    def test_import_mixed_rows(self, ctx):
        r = ctx["client"].post("/api/platform/import/exhibitions", json={"rows": [
            {"title": "2026 智能出行展", "start_date": "2026-11-01T09:00:00",
             "end_date": "2026-11-03T18:00:00", "location": "北京亦创国际会展中心"},
            {"title": "P6基础展会", "start_date": "2026-10-01T09:00:00",   # 标题重复 → 跳过
             "end_date": "2026-10-03T18:00:00", "location": "杭州国际博览中心"},
            {"title": "坏状态展", "start_date": "2026-12-01T09:00:00",
             "end_date": "2026-12-03T18:00:00", "location": "x", "status": "banana"},  # 非法 → 失败
        ]}, headers=ctx["org"])
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["success_count"] == 1 and d["total"] == 3
        by_title = {x["title"]: x for x in d["results"]}
        assert by_title["P6基础展会"]["ok"] is False
        assert by_title["坏状态展"]["ok"] is False

    def test_visitor_cannot_import(self, ctx):
        r = ctx["client"].post("/api/platform/import/exhibitions", json={"rows": [
            {"title": "x展", "start_date": "s", "end_date": "e", "location": "l"}
        ]}, headers=ctx["visitor"])
        assert r.status_code in (401, 403)


class TestOverviewAndJobs:
    def test_overview_admin(self, ctx):
        r = ctx["client"].get("/api/platform/overview", headers=ctx["admin"])
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["exhibitions_count"] >= 2
        assert d["plans_count"] >= 1

    def test_order_expire_job(self, ctx):
        from app.core.jobs import expire_pending_orders
        db = SessionLocal()
        org = db.query(User).filter(User.username == "org_p6").first()
        tt = TicketType(exhibition_id=1, name="过期票", price_cents=100, quota=5)
        db.add(tt); db.commit(); db.refresh(tt)
        stale = TicketingOrder(
            order_no="OSTALE000001", exhibition_id=1, ticket_type_id=tt.id,
            ticket_type_name="过期票", user_id=org.id, amount_cents=100,
            status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),  # 超时
        )
        fresh = TicketingOrder(
            order_no="OFRESH000001", exhibition_id=1, ticket_type_id=tt.id,
            ticket_type_name="过期票", user_id=org.id, amount_cents=100,
            status="pending", created_at=datetime.now(timezone.utc),  # 未超时
        )
        db.add_all([stale, fresh]); db.commit()
        stale_id, fresh_id, tt_id = stale.id, fresh.id, tt.id
        # 过期订单会回退名额：下单时扣了 2 个名额（quota 5→3）
        db.close()

        n = expire_pending_orders(minutes=30)
        assert n == 1  # 只处理过期的

        db = SessionLocal()
        s = db.query(TicketingOrder).filter(TicketingOrder.id == stale_id).first()
        f = db.query(TicketingOrder).filter(TicketingOrder.id == fresh_id).first()
        quota = db.query(TicketType).filter(TicketType.id == tt_id).first().quota
        assert s.status == "cancelled" and s.cancelled_at is not None
        assert f.status == "pending"
        # 订单为 ORM 直插（未走路由扣名额逻辑），任务只做回退：5 + 1 = 6
        assert quota == 6  # 名额回退一个

        # 幂等：再跑一次不再处理
        n2 = expire_pending_orders(minutes=30)
        assert n2 == 0
        db.close()
