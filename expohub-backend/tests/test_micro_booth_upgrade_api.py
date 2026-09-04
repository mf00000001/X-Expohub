"""微展位会员升级 API 测试（隔离测试库）：升级档位闭环 + 权限守卫 + 额度生效

运行: cd expohub-backend && python -m pytest tests/test_micro_booth_upgrade_api.py -v
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.base import SessionLocal
from app.models.micro_booth import MicroBooth
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
    exhibitor = _seed_user(db, f"{tag}_exh", "exhibitor", "华为技术")
    other = _seed_user(db, f"{tag}_oth", "exhibitor", "中兴通讯")
    buyer = _seed_user(db, f"{tag}_buy", "buyer")
    # 展商建微展位
    r = client.post("/api/micro-booths",
                    json={"name": f"升级测试展位-{tag}", "description": "测试", "industry_domain": "电子及家电"},
                    headers=_auth(exhibitor))
    assert r.status_code == 200, r.text
    mb = (r.json()["data"])
    yield {"client": client, "db": db, "exhibitor": exhibitor, "other": other,
           "buyer": buyer, "mb_id": mb["id"], "tag": tag}
    db.close()


def test_upgrade_regular_then_flagship(ctx):
    c, db = ctx["client"], ctx["db"]
    mb_id = ctx["mb_id"]
    db.expire_all()
    mb = db.query(MicroBooth).get(mb_id)
    assert mb.membership_tier == "free"

    # 免费 → regular
    r = c.post(f"/api/micro-booths/{mb_id}/upgrade", json={"tier": "regular"}, headers=_auth(ctx["exhibitor"]))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["membership_tier"] == "regular"
    assert data["product_limit"] == 8

    db.expire_all()
    mb = db.query(MicroBooth).get(mb_id)
    assert mb.membership_tier == "regular"

    # regular → flagship
    r = c.post(f"/api/micro-booths/{mb_id}/upgrade", json={"tier": "flagship"}, headers=_auth(ctx["exhibitor"]))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["membership_tier"] == "flagship"
    assert data["product_limit"] == 50
    assert "flagship" in r.json()["message"]


def test_upgrade_forbidden_for_other_users(ctx):
    c = ctx["client"]
    mb_id = ctx["mb_id"]
    # 另一展商 → 403
    r = c.post(f"/api/micro-booths/{mb_id}/upgrade", json={"tier": "regular"}, headers=_auth(ctx["other"]))
    assert r.status_code == 403
    # 买家 → 403
    r = c.post(f"/api/micro-booths/{mb_id}/upgrade", json={"tier": "regular"}, headers=_auth(ctx["buyer"]))
    assert r.status_code == 403
    # 未登录 → 401
    r = c.post(f"/api/micro-booths/{mb_id}/upgrade", json={"tier": "regular"})
    assert r.status_code == 401


def test_upgrade_rejects_invalid_tier_and_missing_booth(ctx):
    c = ctx["client"]
    mb_id = ctx["mb_id"]
    # 非法档位 → 400
    r = c.post(f"/api/micro-booths/{mb_id}/upgrade", json={"tier": "diamond"}, headers=_auth(ctx["exhibitor"]))
    assert r.status_code == 400
    # 不存在的微展位 → 404
    r = c.post("/api/micro-booths/999999/upgrade", json={"tier": "regular"}, headers=_auth(ctx["exhibitor"]))
    assert r.status_code == 404
    # 未升级成功：仍是 free
    ctx["db"].expire_all()
    mb = ctx["db"].query(MicroBooth).get(mb_id)
    assert mb.membership_tier == "free"


def test_upgrade_unlocks_more_products(ctx):
    """免费版只能挂 3 个展品，升级 regular 后额度提升到 8"""
    c, db = ctx["client"], ctx["db"]
    from app.models.product import Product
    mb_id = ctx["mb_id"]
    # 建 4 个展品
    prods = []
    for i in range(4):
        p = Product(exhibitor_id=ctx["exhibitor"].id, name=f"额度展品{i}", category="电子及家电",
                    status="published", created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc))
        db.add(p)
        db.flush()
        prods.append(p)
    db.commit()

    # 免费版挂第 4 个 → 400（提示升级）
    for p in prods[:3]:
        r = c.post(f"/api/micro-booths/{mb_id}/products", json={"product_id": p.id}, headers=_auth(ctx["exhibitor"]))
        assert r.status_code == 200, r.text
    r = c.post(f"/api/micro-booths/{mb_id}/products", json={"product_id": prods[3].id},
               headers=_auth(ctx["exhibitor"]))
    assert r.status_code == 400
    assert "升级" in r.json()["message"]

    # 升级 regular → 可挂第 4 个
    r = c.post(f"/api/micro-booths/{mb_id}/upgrade", json={"tier": "regular"}, headers=_auth(ctx["exhibitor"]))
    assert r.status_code == 200, r.text
    r = c.post(f"/api/micro-booths/{mb_id}/products", json={"product_id": prods[3].id},
               headers=_auth(ctx["exhibitor"]))
    assert r.status_code == 200, r.text
