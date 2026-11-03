"""category 落库回归：防止「前端传了、后端忽略、接口还返回成功」。

历史问题：Exhibition 模型没有 category 列，Pydantic 默认 extra=ignore
把字段静默丢弃——创建接口返回 200、提示成功，但品类永远是 NULL。
画像的 E1/E2 都以品类为前置，所以这条必须有回归测试。
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.base import SessionLocal
from app.core.security import create_access_token, hash_password
from app.models.user import User


def _auth(user: User) -> dict:
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.id, "role": user.role, "ver": 0})}


@pytest.fixture(scope="module")
def ctx():
    with TestClient(app) as client:
        db = SessionLocal()
        u = User(username="admin_cat", email="admin_cat@test.local",
                 password_hash=hash_password("x"), role="admin", status="active",
                 is_onboarded=True, total_points=0, token_version=0)
        db.add(u)
        db.commit()
        db.refresh(u)
        h = _auth(u)
        db.close()
        yield {"client": client, "admin": h}


def test_create_exhibition_keeps_category(ctx):
    r = ctx["client"].post("/api/exhibitions", headers=ctx["admin"], json={
        "title": "测试品类展", "start_date": "2027-05-01", "end_date": "2027-05-03",
        "location": "上海", "category": "机床工具",
    })
    assert r.status_code == 200, r.text
    data = r.json().get("data") or r.json()
    assert data.get("category") == "机床工具", data


def test_update_exhibition_keeps_category(ctx):
    c = ctx["client"]
    r = c.post("/api/exhibitions", headers=ctx["admin"], json={
        "title": "待改品类展", "start_date": "2027-06-01", "end_date": "2027-06-03",
        "location": "上海", "category": "旧品类",
    })
    eid = (r.json().get("data") or r.json())["id"]
    r2 = c.put("/api/exhibitions/%s" % eid, headers=ctx["admin"], json={"category": "医疗器械"})
    assert r2.status_code == 200, r2.text
    assert (r2.json().get("data") or r2.json()).get("category") == "医疗器械"
