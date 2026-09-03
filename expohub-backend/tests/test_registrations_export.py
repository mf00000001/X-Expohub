"""报名名单 CSV 导出测试（隔离测试库）

运行: cd expohub-backend && python -m pytest tests/test_registrations_export.py -q
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.base import SessionLocal
from app.models.exhibition import Exhibition
from app.models.registration import Registration
from app.models.user import User


def _seed_user(db, username: str, role: str, company: str = "") -> User:
    u = User(
        username=username,
        email=f"{username}@test.local",
        password_hash=hash_password("testpass123"),
        role=role,
        status="active",
        is_onboarded=True,
        company=company or None,
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
def ctx(request):
    tag = request.node.name[:22].replace("::", "_").replace("[", "").replace("]", "")
    with TestClient(app) as c:
        db = SessionLocal()
        org = _seed_user(db, f"{tag}_org", "organizer")
        visitor = _seed_user(db, f"{tag}_vis", "visitor")
        other = _seed_user(db, f"{tag}_oth", "organizer")
        exh = Exhibition(title="导出测试展", start_date="2026-11-01T09:00:00",
                         end_date="2026-11-03T18:00:00", location="广州", status="published",
                         organizer_id=org.id)
        db.add(exh)
        db.commit()
        db.refresh(exh)
        reg = Registration(visitor_id=visitor.id, exhibition_id=exh.id, is_registered=True,
                           is_favorite=False, ticket_code=f"CSV-{tag}",
                           created_at=datetime.now(timezone.utc))
        db.add(reg)
        db.commit()
        yield {"client": c, "db": db, "org": org, "visitor": visitor, "other": other,
               "exh": exh, "reg": reg, "tag": tag}
        db.close()


def test_export_csv_by_owner(ctx):
    c = ctx["client"]
    r = c.get(f"/api/registrations/export?exhibition_id={ctx['exh'].id}", headers=_auth(ctx["org"]))
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert f"registrations_{ctx['exh'].id}.csv" in r.headers.get("content-disposition", "")
    body = r.content.decode("utf-8-sig")
    assert ctx["visitor"].username in body
    assert f"CSV-{ctx['tag']}" in body
    assert body.lstrip("\ufeff").startswith("序号")


def test_export_csv_forbidden_for_other_org(ctx):
    c = ctx["client"]
    r = c.get(f"/api/registrations/export?exhibition_id={ctx['exh'].id}", headers=_auth(ctx["other"]))
    assert r.status_code == 403
