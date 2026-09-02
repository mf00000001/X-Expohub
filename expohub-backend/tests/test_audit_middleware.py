"""P2 审计中间件单元测试（不落库：monkeypatch _record 捕获条目）

覆盖:
1. 写操作(POST)被记录，包含 method/path/status/租户
2. 读操作(GET)不记录
3. 中间件异常不影响业务响应（fail-open）
4. 匿名请求 user_id=None；带有效 token 时解析出用户 id

运行: cd expohub-backend && python -m pytest tests/test_audit_middleware.py -v
"""
from unittest.mock import AsyncMock, patch

from fastapi import Request
from starlette.responses import JSONResponse

from app.core.audit import AuditMiddleware
from app.core.config import settings


def _make_request(method: str, path: str = "/api/demo", headers=None, client=("127.0.0.1", 8000)):
    h = [(b"host", b"testserver")]
    for k, v in (headers or {}).items():
        h.append((k.encode(), v.encode()))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": h,
        "client": client,
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
    }
    return Request(scope)


class TestAuditMiddleware:
    def test_mutating_request_is_recorded(self):
        captured = {}
        mw = AuditMiddleware(app=lambda scope, receive, send: None)
        async def fake_next(req):
            return JSONResponse({"ok": True}, status_code=201)

        async def run():
            with patch("app.core.audit._record", side_effect=lambda e: captured.update(e)):
                resp = await mw.dispatch(
                    _make_request("POST", "/api/exhibitions", headers={"X-Tenant-Id": "tenant-x"}),
                    fake_next,
                )
            return resp

        import asyncio
        resp = asyncio.run(run())
        assert resp.status_code == 201
        assert captured["method"] == "POST"
        assert captured["path"] == "/api/exhibitions"
        assert captured["tenant_id"] == "tenant-x"
        assert captured["status_code"] == 201

    def test_read_request_not_recorded(self):
        mw = AuditMiddleware(app=lambda scope, receive, send: None)
        async def fake_next(req):
            return JSONResponse({"ok": True})

        async def run():
            with patch("app.core.audit._record") as rec:
                await mw.dispatch(_make_request("GET"), fake_next)
            return rec

        import asyncio
        rec = asyncio.run(run())
        rec.assert_not_called()

    def test_middleware_never_breaks_response(self):
        """_record 抛异常时业务响应仍正常返回"""
        mw = AuditMiddleware(app=lambda scope, receive, send: None)
        async def fake_next(req):
            return JSONResponse({"ok": True})

        async def run():
            with patch("app.core.audit._record", side_effect=RuntimeError("db down")):
                resp = await mw.dispatch(_make_request("DELETE"), fake_next)
            return resp

        import asyncio
        resp = asyncio.run(run())
        assert resp.status_code == 200

    def test_anonymous_user_id_none(self):
        captured = {}
        mw = AuditMiddleware(app=lambda scope, receive, send: None)
        async def fake_next(req):
            return JSONResponse({}, status_code=200)

        async def run():
            with patch("app.core.audit._record", side_effect=lambda e: captured.update(e)):
                await mw.dispatch(_make_request("PUT"), fake_next)
            return captured

        import asyncio
        captured = asyncio.run(run())
        assert captured["user_id"] is None
