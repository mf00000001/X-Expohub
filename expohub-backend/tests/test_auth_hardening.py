r"""认证接口安全硬化回归测试（隔离测试库 pytest_expohub.db）

覆盖 app/modules/identity/auth.py 的三处硬化，全部走 TestClient(app) 真实路由：
1. login() 拒绝 status='disabled'（已注销/被禁用）的账号 → 401，且不返回令牌。
2. register() 强制 privacy_agreed=true：字段缺失或显式 false → 400，
   提示语含「同意」或「隐私政策」关键字（不断言全文，避免文案微调即挂）。
3. register() 拒绝占用已注销账号的匿名化标识：
   - username 以 deleted_ 开头 → 400；
   - email 域名为 deleted.local（x@deleted.local）→ 400。
4. 正面用例：正常用户名/邮箱 + privacy_agreed=true → 200，
   返回的 user 中 privacy_agreed_at 非空（同意留痕）。

数据策略：conftest.py 在本文件导入前已把 DATABASE_URL 指向独立测试库
并删除旧库文件，表由 TestClient 启动期 create_all 创建；因此不需要逐条清理，
只需保证用户名/邮箱唯一（uuid 后缀），避免与其它用例冲突。

运行: cd expohub-backend && ..\.venv\Scripts\python.exe -m pytest tests/test_auth_hardening.py -q
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import hash_password
from app.models.base import SessionLocal
from app.models.user import User

PASSWORD = "testpass123"


def _uniq(prefix: str) -> str:
    """唯一后缀用户名/邮箱前缀，避免跨用例唯一约束冲突"""
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _seed_user(db, username: str, status: str = "active") -> User:
    """直接种库：与 test_registrations_export.py 的 _seed_user 同款写法"""
    u = User(
        username=username,
        email=f"{username}@test.local",
        password_hash=hash_password(PASSWORD),
        role="visitor",
        status=status,
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


def _register_payload(username: str, email: str, **overrides) -> dict:
    payload = {"username": username, "email": email, "password": PASSWORD}
    payload.update(overrides)
    return payload


@pytest.fixture()
def client():
    """先进入 TestClient（触发 lifespan → create_all），再让用例拿 db"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(client):
    session = SessionLocal()
    yield session
    session.close()


# ============================================================
# 1) login 拒绝 disabled 账号
# ============================================================

def test_login_rejects_disabled(client, db):
    """disabled（已注销/被禁用）账号即使密码正确也不得登录"""
    username = _uniq("disabled")
    _seed_user(db, username, status="disabled")

    r = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})

    assert r.status_code == 401, r.text
    body = r.json()
    assert body.get("success") is False
    # 关键：拒绝时绝不能下发令牌
    assert "access_token" not in r.text
    # 密码正确也拒绝，说明拦截来自状态校验而不是密码校验
    assert body.get("code") == "UNAUTHORIZED"


# ============================================================
# 2) register 强制 privacy_agreed=true
# ============================================================

@pytest.mark.parametrize("agreed", [None, False], ids=["missing", "false"])
def test_register_requires_privacy_agreed(client, db, agreed):
    """不带 privacy_agreed 或传 false → 400（不默认同意）"""
    username = _uniq("privacy")
    email = f"{username}@test.local"
    overrides = {} if agreed is None else {"privacy_agreed": agreed}

    r = client.post("/api/auth/register", json=_register_payload(username, email, **overrides))

    assert r.status_code == 400, r.text
    body = r.json()
    assert body.get("success") is False
    assert body.get("code") == "BAD_REQUEST"
    # 文案用关键字断言：允许「同意」「隐私政策」任一出现
    text = f"{body.get('message') or ''}{body.get('detail') or ''}"
    assert ("同意" in text) or ("隐私政策" in text), text
    # 拒绝必须发生在建号之前：库里不应留下该用户
    db.expire_all()
    assert db.query(User).filter(User.username == username).first() is None


# ============================================================
# 3) register 拒绝已注销账号的匿名化标识
# ============================================================

def test_register_rejects_deleted_username(client, db):
    """username 以 deleted_ 开头（已注销匿名化前缀）→ 400，防止 lookalike 占用"""
    username = f"deleted_{uuid.uuid4().hex[:8]}"
    email = f"{_uniq('deluname')}@test.local"

    r = client.post(
        "/api/auth/register",
        json=_register_payload(username, email, privacy_agreed=True),
    )

    assert r.status_code == 400, r.text
    body = r.json()
    assert body.get("success") is False
    assert body.get("code") == "BAD_REQUEST"
    assert "用户名" in (body.get("message") or "")
    db.expire_all()
    assert db.query(User).filter(User.username == username).first() is None


def test_register_rejects_deleted_email_domain(client, db):
    """email 域名为 deleted.local → 400，防止冒充已注销账号邮箱"""
    local = _uniq("delmail")
    email = f"{local}@deleted.local"
    username = _uniq("delmailuser")

    r = client.post(
        "/api/auth/register",
        json=_register_payload(username, email, privacy_agreed=True),
    )

    assert r.status_code == 400, r.text
    body = r.json()
    assert body.get("success") is False
    assert body.get("code") == "BAD_REQUEST"
    assert "邮箱" in (body.get("message") or "")
    db.expire_all()
    assert db.query(User).filter(User.email == email).first() is None


# ============================================================
# 4) 正面用例：同意隐私政策后注册成功并留痕
# ============================================================

def test_register_with_privacy_agreed_succeeds(client, db):
    """正常用户名/邮箱 + privacy_agreed=true → 200，且 privacy_agreed_at 非空"""
    username = _uniq("happy")
    email = f"{username}@test.local"

    r = client.post(
        "/api/auth/register",
        json=_register_payload(username, email, privacy_agreed=True),
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    data = body["data"]
    assert data["user"]["username"] == username
    assert data["user"]["email"] == email
    # 同意留痕：响应与数据库都必须有值
    assert data["user"]["privacy_agreed_at"]
    db.expire_all()
    row = db.query(User).filter(User.username == username).first()
    assert row is not None
    assert row.privacy_agreed_at is not None
    # 注册成功即可登录（未被硬化逻辑误伤）
    r2 = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["access_token"]
