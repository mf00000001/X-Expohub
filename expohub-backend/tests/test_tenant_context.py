"""P2 多租户上下文单元测试

覆盖:
1. 缺省回落默认租户（向后兼容：存量请求不带 X-Tenant-Id）
2. 显式租户头解析
3. TENANT_REQUIRED=True 时缺失租户头抛 422
4. ContextVar 注入/读取

运行: cd expohub-backend && python -m pytest tests/test_tenant_context.py -v
"""
import pytest

from app.core.config import settings
from app.core.tenant import (
    TenantContext,
    resolve_tenant,
    get_tenant_context,
    set_tenant_context,
    X_TENANT_HEADER,
)


class TestResolveTenant:
    def test_missing_header_falls_back_to_default(self):
        ctx = resolve_tenant(None)
        assert ctx.tenant_id == settings.TENANT_DEFAULT
        assert ctx.explicit is False

    def test_empty_header_falls_back_to_default(self):
        ctx = resolve_tenant("   ")
        assert ctx.tenant_id == settings.TENANT_DEFAULT

    def test_explicit_tenant(self):
        ctx = resolve_tenant("tenant-a")
        assert ctx.tenant_id == "tenant-a"
        assert ctx.explicit is True

    def test_explicit_tenant_strips_whitespace(self):
        ctx = resolve_tenant("  tenant-b  ")
        assert ctx.tenant_id == "tenant-b"

    def test_required_mode_raises_when_missing(self, monkeypatch):
        monkeypatch.setattr(settings, "TENANT_REQUIRED", True)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            resolve_tenant(None)
        assert ei.value.status_code == 422

    def test_required_mode_allows_explicit(self, monkeypatch):
        monkeypatch.setattr(settings, "TENANT_REQUIRED", True)
        ctx = resolve_tenant("tenant-c")
        assert ctx.tenant_id == "tenant-c"


class TestTenantContextVar:
    def test_default_when_unset(self):
        ctx = get_tenant_context()
        assert ctx.tenant_id == settings.TENANT_DEFAULT

    def test_set_and_get(self):
        set_tenant_context(TenantContext(tenant_id="t-1", explicit=True))
        assert get_tenant_context().tenant_id == "t-1"
        # 复位
        set_tenant_context(TenantContext())
