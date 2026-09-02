"""
审计日志（P2）

- AuditLog 模型：记录写操作（POST/PUT/PATCH/DELETE）的 人/租户/动作/结果。
- AuditMiddleware：纯观测中间件，任何异常都不会影响业务请求；
  默认仅记录写操作，GET/HEAD/OPTIONS 跳过；
  未解析到登录用户时 user_id 为 None（匿名写操作同样留痕）。
- 兼容说明：新增表由启动期 Base.metadata.create_all 自动创建，存量表不受影响。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from sqlalchemy import Column, Integer, String, DateTime, Text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.tenant import X_TENANT_HEADER, get_header
from app.models.base import Base, SessionLocal
from app.core.security import verify_token

# 只审计“写操作”
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditLog(Base):
    """审计日志表（P2 新增）"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), default=settings.TENANT_DEFAULT, index=True)
    user_id = Column(Integer, nullable=True, index=True)          # 可空：匿名写操作
    action = Column(String(64), nullable=False)                   # e.g. POST /api/login
    method = Column(String(8), nullable=False)
    path = Column(String(255), nullable=False)
    status_code = Column(Integer, nullable=False)
    client_ip = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    detail = Column(Text, nullable=True)                          # 小体量请求体/摘要
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def _extract_user_id(request: Request) -> Optional[int]:
    """从 Authorization Bearer 中尽力解析用户 id；失败返回 None（不抛异常）"""
    auth = request.headers.get("authorization")
    if not auth:
        return None
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        payload = verify_token(token)
        if payload.get("type") != "access":
            return None
        return int(payload.get("sub"))
    except Exception:
        return None


def _record(entry: dict) -> None:
    """独立会话落库；失败仅打印，绝不向上抛（审计不影响业务）"""
    try:
        db = SessionLocal()
        try:
            db.add(AuditLog(**entry))
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover
        import sys
        print(f"[audit] write failed: {exc}", file=sys.stderr)


class AuditMiddleware(BaseHTTPMiddleware):
    """写操作审计中间件（可开关：settings.AUDIT_ENABLED）"""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        try:
            if settings.AUDIT_ENABLED and request.method in _MUTATING_METHODS:
                body_bits = []
                detail = None
                if settings.AUDIT_BODY_MAX and request.method in ("POST", "PUT", "PATCH"):
                    try:
                        raw = (await request.body())[: settings.AUDIT_BODY_MAX]
                        if raw:
                            body_bits.append(raw.decode("utf-8", errors="replace"))
                    except Exception:
                        pass
                if body_bits:
                    detail = " ".join(body_bits)[: settings.AUDIT_BODY_MAX]
                _record({
                    "tenant_id": get_header(request, X_TENANT_HEADER) or settings.TENANT_DEFAULT,
                    "user_id": _extract_user_id(request),
                    "action": f"{request.method} {request.url.path}",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": (request.headers.get("user-agent") or "")[:255] or None,
                    "detail": detail,
                })
        except Exception as exc:  # pragma: no cover
            import sys
            print(f"[audit] middleware error: {exc}", file=sys.stderr)
        return response
