"""展品编辑/删除 API 测试（隔离测试库）：创建者可改删、越权 403、404、匿名 401

运行: cd expohub-backend && python -m pytest tests/test_products_api.py -v
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.base import SessionLocal
from app.models.product import Product
from app.models.user import User


def _seed_user(db, username: str, role: str, company: str = "测试公司") -> User:
    u = User(
        username=username,
        email=f"{username}@test.local",
        password_hash=hash_password("testpass123"),
        role=role,
        status="active",
        is_onboarded=True,
        company=company,
        total_points=0,
        token_version=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
    # 用户名按用例名生成，避免跨用例耦合（同名唯一约束）
    tag = request.node.name[:20].replace("::", "_").replace("[", "").replace("]", "")
    db = SessionLocal()
    owner = _seed_user(db, f"{tag}_own", "exhibitor", "原创科技")
    other = _seed_user(db, f"{tag}_oth", "exhibitor", "别人公司")
    p = Product(exhibitor_id=owner.id, name=f"待编辑展品-{tag}", category="电子及家电",
                description="原描述", price=100.0, status="draft",
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    db.add(p)
    db.commit()
    db.refresh(p)
    yield {"client": client, "db": db, "owner": owner, "other": other, "product_id": p.id, "tag": tag}
    db.close()


def test_owner_updates_product(ctx):
    c, db = ctx["client"], ctx["db"]
    pid = ctx["product_id"]
    r = c.put(f"/api/products/{pid}",
              json={"name": "改名后的展品", "description": "新描述",
                    "category": "AI/科技", "status": "published"},
              headers=_auth(ctx["owner"]))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["name"] == "改名后的展品"
    assert data["description"] == "新描述"
    assert data["category"] == "AI/科技"
    assert data["status"] == "published"
    db.expire_all()
    assert db.query(Product).get(pid).name == "改名后的展品"


def test_price_update_persists_but_hidden_publicly(ctx):
    """平台按询盘设计：公开 API 刻意隐藏报价(price=None)，但展商更新价格应落库"""
    c, db = ctx["client"], ctx["db"]
    pid = ctx["product_id"]
    r = c.put(f"/api/products/{pid}", json={"price": 999.5}, headers=_auth(ctx["owner"]))
    assert r.status_code == 200, r.text
    # 公开响应不透露价格（设计如此）
    assert r.json()["data"]["price"] is None
    # 数据库层面已更新
    db.expire_all()
    assert db.query(Product).get(pid).price == 999.5


def test_other_exhibitor_cannot_update_or_delete(ctx):
    c = ctx["client"]
    pid = ctx["product_id"]
    r = c.put(f"/api/products/{pid}", json={"name": "篡改"}, headers=_auth(ctx["other"]))
    assert r.status_code == 403
    r = c.delete(f"/api/products/{pid}", headers=_auth(ctx["other"]))
    assert r.status_code == 403


def test_owner_deletes_product(ctx):
    c, db = ctx["client"], ctx["db"]
    pid = ctx["product_id"]
    r = c.delete(f"/api/products/{pid}", headers=_auth(ctx["owner"]))
    assert r.status_code == 200, r.text
    assert "已删除" in r.json()["message"]
    assert db.query(Product).filter(Product.id == pid).first() is None


def test_product_edit_guards(ctx):
    c = ctx["client"]
    pid = ctx["product_id"]
    # 不存在 → 404
    r = c.put("/api/products/999999", json={"name": "x"}, headers=_auth(ctx["owner"]))
    assert r.status_code == 404
    # 匿名 → 401
    r = c.put(f"/api/products/{pid}", json={"name": "x"})
    assert r.status_code == 401
    r = c.delete(f"/api/products/{pid}")
    assert r.status_code == 401
