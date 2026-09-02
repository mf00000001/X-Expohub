"""
多租户上下文（P2）

提供租户解析与请求级上下文：
- 从 X-Tenant-Id 请求头解析租户；
- 缺省回落 settings.TENANT_DEFAULT（向后兼容：存量单租户请求不受影响）；
- settings.TENANT_REQUIRED=True 时缺失租户头直接 422。

默认行为不变：未启用强制校验时，不带头部的请求 = 默认租户。
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

from fastapi import HTTPException, Request

from app.core.config import settings

X_TENANT_HEADER = "X-Tenant-Id"


def get_header(request: Request, name: str) -> Optional[str]:
    """大小写不敏感地读取请求头（规避部分 Starlette 版本 Headers.get 的 case bug）"""
    ln = name.lower()
    for k, v in request.headers.items():
        if k.lower() == ln:
            return v
    return None


@dataclass
class TenantContext:
    """当前请求的租户上下文"""
    tenant_id: str = settings.TENANT_DEFAULT
    # 是否由调用方显式指定（False = 回落默认租户）
    explicit: bool = False
    attrs: dict = field(default_factory=dict)


_tenant_ctx: ContextVar[Optional[TenantContext]] = ContextVar("tenant_ctx", default=None)


def set_tenant_context(ctx: TenantContext) -> None:
    """在请求处理过程中写入租户上下文（由中间件或依赖调用）"""
    _tenant_ctx.set(ctx)


def get_tenant_context() -> TenantContext:
    """读取当前请求租户上下文（无则返回默认租户）"""
    ctx = _tenant_ctx.get()
    if ctx is None:
        ctx = TenantContext()
        _tenant_ctx.set(ctx)
    return ctx


def resolve_tenant(x_tenant_id: Optional[str]) -> TenantContext:
    """将请求头解析为租户上下文"""
    if x_tenant_id and x_tenant_id.strip():
        return TenantContext(tenant_id=x_tenant_id.strip(), explicit=True)
    if settings.TENANT_REQUIRED:
        raise HTTPException(status_code=422, detail=f"缺少租户头 {X_TENANT_HEADER}")
    return TenantContext()  # 默认租户


async def get_tenant(request: Request) -> TenantContext:
    """FastAPI 依赖：注入当前租户（用于新域端点）"""
    x_tenant_id = get_header(request, X_TENANT_HEADER)
    ctx = resolve_tenant(x_tenant_id)
    set_tenant_context(ctx)
    return ctx
