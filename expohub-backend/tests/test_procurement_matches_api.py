"""应标闭环 API 测试（隔离测试库）：买家接受应标 → 撮合完成；权限与幂等守卫

运行: cd expohub-backend && python -m pytest tests/test_procurement_matches_api.py -v
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.base import SessionLocal
from app.models.procurement import Procurement
from app.models.procurement_match import ProcurementMatch
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
    buyer = _seed_user(db, f"{tag}_buyer", "buyer")
    exhibitor = _seed_user(db, f"{tag}_exh", "exhibitor", "华为技术")
    proc = Procurement(
        purchaser_id=buyer.id, purchaser_name="测试买家", title=f"应标闭环测试需求-{tag}",
        category="电子及家电", status="pending",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(proc)
    db.commit()
    db.refresh(proc)
    product = Product(
        exhibitor_id=exhibitor.id, name="测试展品", category="电子及家电", status="published",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    yield {"client": client, "db": db, "buyer": buyer, "exhibitor": exhibitor,
           "proc": proc, "product": product, "tag": tag}
    db.close()


def test_exhibitor_bids_then_buyer_accepts(ctx):
    c, db = ctx["client"], ctx["db"]
    proc = db.query(Procurement).filter(Procurement.id == ctx["proc"].id).first()

    # 展商应标
    r = c.post(f"/api/procurements/{proc.id}/matches",
               json={"product_id": ctx["product"].id, "message": "可定制，15天交付", "quoted_price": 88000},
               headers=_auth(ctx["exhibitor"]))
    assert r.status_code == 200, r.text

    # 买家查看应标列表
    r = c.get(f"/api/procurements/{proc.id}/matches", headers=_auth(ctx["buyer"]))
    assert r.status_code == 200, r.text
    matches = (r.json().get("data") or {}).get("matches") or r.json().get("data") or []
    assert matches, "应标列表应为空以外的记录"
    match_id = matches[0]["id"]

    # 非买家(展商)接受 → 403
    r = c.post(f"/api/procurements/{proc.id}/matches/{match_id}/accept", headers=_auth(ctx["exhibitor"]))
    assert r.status_code == 403

    # 买家接受 → 撮合完成
    r = c.post(f"/api/procurements/{proc.id}/matches/{match_id}/accept", headers=_auth(ctx["buyer"]))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["procurement"]["status"] == "completed"
    assert data["match"]["is_accepted"] is True

    # 重复接受 → 400（已被接受）
    r = c.post(f"/api/procurements/{proc.id}/matches/{match_id}/accept", headers=_auth(ctx["buyer"]))
    assert r.status_code == 400


def test_accept_rejects_sibling_matches(ctx):
    c, db = ctx["client"], ctx["db"]
    proc = db.query(Procurement).filter(Procurement.id == ctx["proc"].id).first()
    tag = ctx["tag"]
    db.add(ProcurementMatch(procurement_id=proc.id, exhibitor_id=ctx["exhibitor"].id,
                            product_id=ctx["product"].id, message="投标1"))
    db.commit()

    # 另一展商也投标
    ex2 = _seed_user(db, f"{tag}_exh2", "exhibitor", "中兴通讯")
    p2 = Product(exhibitor_id=ex2.id, name="展品2", category="电子及家电", status="published",
                 created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    db.add(p2)
    db.commit()
    db.refresh(p2)
    r = c.post(f"/api/procurements/{proc.id}/matches",
               json={"product_id": p2.id, "message": "性价比方案"},
               headers=_auth(ex2))
    assert r.status_code == 200, r.text

    match1 = db.query(ProcurementMatch).filter(ProcurementMatch.procurement_id == proc.id,
                                               ProcurementMatch.exhibitor_id == ctx["exhibitor"].id).first()
    r = c.post(f"/api/procurements/{proc.id}/matches/{match1.id}/accept", headers=_auth(ctx["buyer"]))
    assert r.status_code == 200, r.text

    # 兄弟投标自动落选（is_accepted=False），采购完成
    db.expire_all()
    m1 = db.query(ProcurementMatch).get(match1.id)
    others = db.query(ProcurementMatch).filter(
        ProcurementMatch.procurement_id == proc.id,
        ProcurementMatch.id != match1.id).all()
    assert m1.is_accepted is True
    assert all(o.is_accepted is False for o in others)
    assert db.query(Procurement).get(proc.id).status == "completed"
