"""展会时间线筛选（timeline）+ 参展展商名录 API 测试（隔离测试库）

覆盖：
1. GET /exhibitions?timeline=ended|upcoming —— 按日期推导的时间线筛选与排序；
2. GET /exhibitions/upcoming —— 只返回未来开始的已发布展会（修复前会把已结束的排前面）；
3. GET /exhibitions/{id}/exhibitors —— 展商名录去重/分页/字段完整性；
4. GET /exhibitions/{id} 详情内嵌 exhibitor_count。

运行: cd expohub-backend && python -m pytest tests/test_exhibitions_timeline_exhibitors.py -v
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import hash_password
from app.models.base import SessionLocal
from app.models.booth import Booth
from app.models.exhibition import Exhibition
from app.models.product import Product
from app.models.user import User


def _seed_user(db, username: str, company: str, industry: str = "机械", region: str = "北京市") -> User:
    u = User(
        username=username,
        email=f"{username}@test.local",
        password_hash=hash_password("testpass123"),
        role="exhibitor",
        status="active",
        is_onboarded=True,
        company=company,
        industry_domain=industry,
        region=region,
        total_points=0,
        token_version=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _seed_exhibition(db, title: str, start: str, end: str, status: str = "published") -> Exhibition:
    e = Exhibition(
        title=title,
        description=f"{title} 测试",
        start_date=start,
        end_date=end,
        location="测试会展中心（测试路 1 号）",
        is_featured=False,
        hot_score=0,
        visitor_count=0,
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _seed_booth(db, exhibition_id: int, exhibitor_id, booth_number: str, company: str | None = None):
    b = Booth(
        exhibition_id=exhibition_id,
        exhibitor_id=exhibitor_id,
        booth_number=booth_number,
        exhibitor_name=company,
        company_name=company,
        size="6x6m",
        location_area="A馆·测试展区",
        price=12000.0,
        status="occupied" if exhibitor_id else "available",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_timeline_filter(request, client):
    """timeline=ended/upcoming 按日期正确过滤，且排除了无关展会"""
    tag = f"tl{request.node.name}".replace("[", "").replace("]", "")
    db = SessionLocal()
    try:
        _seed_exhibition(db, f"{tag}-历史展", "2020-01-01T09:00:00+08:00", "2020-01-03T18:00:00+08:00")
        _seed_exhibition(db, f"{tag}-未来展", "2099-01-01T09:00:00+08:00", "2099-01-03T18:00:00+08:00")
    finally:
        db.close()

    r = client.get("/api/exhibitions", params={"timeline": "ended", "search": tag})
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()["data"]["list"]]
    assert f"{tag}-历史展" in titles
    assert f"{tag}-未来展" not in titles

    r = client.get("/api/exhibitions", params={"timeline": "upcoming", "search": tag})
    titles = [x["title"] for x in r.json()["data"]["list"]]
    assert f"{tag}-未来展" in titles
    assert f"{tag}-历史展" not in titles


def test_upcoming_endpoint_future_only(request, client):
    """修复验证：已结束的已发布展会不再出现在 /exhibitions/upcoming"""
    tag = f"up{request.node.name}".replace("[", "").replace("]", "")
    db = SessionLocal()
    try:
        _seed_exhibition(db, f"{tag}-结束的", "2020-01-01T09:00:00+08:00", "2020-01-03T18:00:00+08:00")
        _seed_exhibition(db, f"{tag}-未来的", "2099-02-01T09:00:00+08:00", "2099-02-03T18:00:00+08:00")
        _seed_exhibition(db, f"{tag}-草稿未来", "2099-03-01T09:00:00+08:00", "2099-03-03T18:00:00+08:00", status="draft")
    finally:
        db.close()

    r = client.get("/api/exhibitions/upcoming")
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()["data"]]
    assert f"{tag}-未来的" in titles
    assert f"{tag}-结束的" not in titles
    assert f"{tag}-草稿未来" not in titles


def test_exhibitors_endpoint(request, client):
    """展商名录：按展商去重、分页、字段、详情 exhibitor_count"""
    tag = f"ex{request.node.name}".replace("[", "").replace("]", "")
    db = SessionLocal()
    try:
        exh = _seed_exhibition(db, f"{tag}-展商测试展", "2026-01-01T09:00:00+08:00", "2026-01-03T18:00:00+08:00")
        u1 = _seed_user(db, f"{tag}_sup1", f"{tag}一号供应商", industry="机械", region="陕西省")
        u2 = _seed_user(db, f"{tag}_sup2", f"{tag}二号供应商", industry="电子及家电", region="广东省")
        # u1 两个展位（应去重），u2 一个
        _seed_booth(db, exh.id, u1.id, "A-001", f"{tag}一号供应商")
        _seed_booth(db, exh.id, u1.id, "A-002", f"{tag}一号供应商")
        _seed_booth(db, exh.id, u2.id, "A-003", f"{tag}二号供应商")
        _seed_booth(db, exh.id, None, "A-004")  # 可用展位不计入
        db.add(Product(exhibitor_id=u1.id, name=f"{tag}-展品1", category="机械", price=100.0,
                       status="published", created_at=datetime.now(timezone.utc),
                       updated_at=datetime.now(timezone.utc)))
        db.commit()
        exh_id = exh.id
    finally:
        db.close()

    r = client.get(f"/api/exhibitions/{exh_id}/exhibitors", params={"page": 1, "page_size": 10})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 2  # 去重后 2 家
    items = data["list"]
    assert len(items) == 2
    by_company = {i["company"]: i for i in items}
    a = by_company[f"{tag}一号供应商"]
    assert a["booth_number"] == "A-001"  # 保留展位号最小者
    assert a["products_count"] == 1
    assert a["region"] == "陕西省"
    b = by_company[f"{tag}二号供应商"]
    assert b["industry_domain"] == "电子及家电"

    # 分页：page_size=1 → 2 页
    r = client.get(f"/api/exhibitions/{exh_id}/exhibitors", params={"page": 2, "page_size": 1})
    data = r.json()["data"]
    assert data["total"] == 2 and len(data["list"]) == 1

    # 详情内嵌 exhibitor_count
    r = client.get(f"/api/exhibitions/{exh_id}")
    assert r.json()["data"]["exhibitor_count"] == 2

    # 无展位的展会 → total 0
    db = SessionLocal()
    try:
        empty = _seed_exhibition(db, f"{tag}-空展会", "2026-05-01T09:00:00+08:00", "2026-05-03T18:00:00+08:00")
        empty_id = empty.id
    finally:
        db.close()
    r = client.get(f"/api/exhibitions/{empty_id}/exhibitors")
    assert r.json()["data"]["total"] == 0

    # 不存在的展会 → 404
    r = client.get("/api/exhibitions/99999999/exhibitors")
    assert r.status_code == 404
