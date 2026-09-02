"""P5 AI 原生层测试（隔离测试库）

覆盖:
1. 无 key 默认 mock：/api/ai/generate 返回 mock provider + degraded
2. PII 脱敏：redact_pii 对手机号/邮箱/身份证/长数字脱敏
3. 用法记账：generate 后 usage/me 有记录（mock cost=0）
4. 预算护栏：预算为 0 上限时返回 400
5. 未知能力 400

运行: cd expohub-backend && python -m pytest tests/test_ai_api.py -v
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.base import SessionLocal
from app.models.user import User
from app.modules.ai.pii import redact_pii


def _seed_user(db, username: str, role: str = "visitor") -> User:
    u = User(
        username=username, email=f"{username}@test.local",
        password_hash=hash_password("x"), role=role, status="active",
        is_onboarded=True, total_points=0, token_version=0,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


@pytest.fixture(scope="module")
def ctx():
    with TestClient(app) as client:
        db = SessionLocal()
        u = _seed_user(db, "ai_user")
        h = {"Authorization": f"Bearer {create_access_token({'sub': u.id, 'role': u.role, 'ver': 0})}"}
        db.close()
        yield {"client": client, "auth": h}


class TestRedactPii:
    def test_phone_masked(self):
        out = redact_pii("联系我 13812345678 谢谢")
        assert "13812345678" not in out
        assert "138****5678" in out

    def test_email_masked(self):
        out = redact_pii("邮箱 zhangsan@example.com 收")
        assert "zhangsan@example.com" not in out
        assert "zh***@***" in out

    def test_idcard_and_longnum_masked(self):
        out = redact_pii("身份证 110101199003077777，卡号 6222020200112233445")
        assert "110101199003077777" not in out
        assert "6222020200112233445" not in out


class TestGenerate:
    def test_mock_provider_when_no_key(self, ctx):
        assert settings.AI_PROVIDER == "mock"
        r = ctx["client"].post("/api/ai/generate", json={
            "capability": "reason", "prompt": "帮我写一段展会推荐理由",
        }, headers=ctx["auth"])
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["provider"] == "mock"
        assert d["degraded"] is True
        assert "reason" in d["content"]

    def test_unknown_capability_400(self, ctx):
        r = ctx["client"].post("/api/ai/generate", json={
            "capability": "magic", "prompt": "hi",
        }, headers=ctx["auth"])
        assert r.status_code == 400

    def test_unauthenticated_401(self, ctx):
        r = ctx["client"].post("/api/ai/generate", json={"capability": "qa", "prompt": "hi"})
        assert r.status_code in (401, 403)

    def test_usage_recorded(self, ctx):
        r = ctx["client"].get("/api/ai/usage/me", headers=ctx["auth"])
        assert r.status_code == 200
        d = r.json()["data"]
        assert len(d["list"]) >= 1
        assert d["list"][0]["provider"] == "mock"
        assert d["list"][0]["prompt_chars"] > 0

    def test_budget_guard(self, ctx, monkeypatch):
        # 造一条本月高额用量，并把预算压到 5 分 → 拦截
        db = SessionLocal()
        from app.modules.ai.models import AiUsageLog
        log = AiUsageLog(capability="qa", provider="mock", user_id=1,
                         degraded=1, prompt_chars=10, response_chars=10, cost_cents=100)
        db.add(log); db.commit(); log_id = log.id
        db.close()
        try:
            monkeypatch.setattr(settings, "AI_MONTHLY_BUDGET_CENTS", 5)
            r = ctx["client"].post("/api/ai/generate", json={
                "capability": "qa", "prompt": "hi again",
            }, headers=ctx["auth"])
            monkeypatch.setattr(settings, "AI_MONTHLY_BUDGET_CENTS", 10000)
            assert r.status_code == 400
            assert "预算" in r.json()["message"]
        finally:
            db = SessionLocal()
            db.query(AiUsageLog).filter(AiUsageLog.id == log_id).delete()
            db.commit(); db.close()
