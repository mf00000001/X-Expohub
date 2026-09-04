"""埋点上报 API 测试（隔离测试库）：page_view/favorite 计数、当日去重、同步展品/微展位计数

运行: cd expohub-backend && python -m pytest tests/test_analytics_track_api.py -v
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.analytics import AnalyticsEvent
from app.models.base import SessionLocal
from app.models.product import Product
from app.models.user import User


def _seed_user(db, username: str, role: str = "exhibitor") -> User:
    u = User(
        username=username, email=f"{username}@test.local",
        password_hash=hash_password("testpass123"), role=role,
        status="active", is_onboarded=True, company="埋点科技",
        total_points=0, token_version=0,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id, 'role': user.role, 'ver': 0})}"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def ctx(request, client):
    tag = request.node.name[:20].replace("::", "_").replace("[", "").replace("]", "")
    db = SessionLocal()
    owner = _seed_user(db, f"{tag}_own")
    p = Product(exhibitor_id=owner.id, name=f"埋点展品-{tag}", category="AI/科技", status="published",
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    db.add(p)
    db.commit()
    db.refresh(p)
    yield {"client": client, "db": db, "owner": owner, "product_id": p.id}
    db.close()


def _track(c, etype, entity, eid, owner_id):
    return c.post("/api/analytics/event",
                  json={"event_type": etype, "entity_type": entity, "entity_id": eid,
                        "source_user_id": owner_id})


def test_page_view_counts_and_dedups_same_day(ctx):
    c, db = ctx["client"], ctx["db"]
    pid = ctx["product_id"]
    # 第一次浏览 → 落库并计数
    r = _track(c, "page_view", "product", pid, ctx["owner"].id)
    assert r.status_code == 200
    db.expire_all()
    p = db.query(Product).get(pid)
    assert p.view_count == 1
    assert db.query(AnalyticsEvent).filter(AnalyticsEvent.entity_id == pid).count() == 1

    # 当天重复浏览 → dedup：不再计数、不再落库
    r = _track(c, "page_view", "product", pid, ctx["owner"].id)
    assert r.status_code == 200
    assert r.json()["message"] == "dedup"
    db.expire_all()
    p = db.query(Product).get(pid)
    assert p.view_count == 1
    assert db.query(AnalyticsEvent).filter(AnalyticsEvent.entity_id == pid).count() == 1


def test_favorite_event_increments_product_favorite_count(ctx):
    c, db = ctx["client"], ctx["db"]
    pid = ctx["product_id"]
    r = _track(c, "favorite", "product", pid, ctx["owner"].id)
    assert r.status_code == 200
    db.expire_all()
    p = db.query(Product).get(pid)
    assert p.favorite_count == 1


def test_overview_and_trend_reflect_events(ctx):
    c = ctx["client"]
    pid = ctx["product_id"]
    uid = ctx["owner"].id
    h = _auth(ctx["owner"])
    _track(c, "page_view", "product", pid, uid)
    _track(c, "favorite", "product", pid, uid)

    ov = c.get("/api/exhibitor/analytics/overview", headers=h)
    assert ov.status_code == 200
    data = ov.json()["data"]
    assert data["today"]["views"] >= 1
    assert data["today"]["favorites"] >= 1
    assert data["total"]["views"] >= 1

    tr = c.get("/api/exhibitor/analytics/trend?days=7", headers=h)
    assert tr.status_code == 200
    trend = tr.json()["data"]
    assert len(trend) == 7
    assert trend[-1]["views"] >= 1  # 今天有浏览


def test_event_anonymous_ok_and_validation(ctx):
    c = ctx["client"]
    pid = ctx["product_id"]
    # 未登录也可埋点（页面 fire-and-forget）
    r = c.post("/api/analytics/event",
               json={"event_type": "page_view", "entity_type": "product",
                     "entity_id": pid, "source_user_id": ctx["owner"].id})
    assert r.status_code == 200
    # 缺字段 → 422
    r = c.post("/api/analytics/event", json={"event_type": "page_view"})
    assert r.status_code == 422
