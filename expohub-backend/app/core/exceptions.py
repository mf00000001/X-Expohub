"""
自定义异常与全局异常处理器

定义业务层异常类型，并在 FastAPI 中统一处理为 HTTP 响应。
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
)


class AppException(Exception):
    """应用基础异常

    Attributes:
        message: 错误描述
        code: 业务错误码（可选）
        status_code: HTTP 状态码
        detail: 错误详情（可选）
    """

    def __init__(
        self,
        message: str = "服务器内部错误",
        code: Optional[str] = None,
        status_code: int = HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Optional[Any] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


class NotFound(AppException):
    """资源不存在"""

    def __init__(self, message: str = "资源不存在", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=HTTP_404_NOT_FOUND,
            detail=detail,
        )


class BadRequest(AppException):
    """请求参数错误"""

    def __init__(self, message: str = "请求参数错误", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code="BAD_REQUEST",
            status_code=HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class Unauthorized(AppException):
    """未认证或令牌无效"""

    def __init__(self, message: str = "请先登录", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=HTTP_401_UNAUTHORIZED,
            detail=detail,
            # FastAPI 需要这个 header 来触发浏览器的认证弹窗
        )

    @property
    def headers(self) -> dict[str, str]:
        return {"WWW-Authenticate": "Bearer"}


class Forbidden(AppException):
    """权限不足"""

    def __init__(self, message: str = "权限不足，无法执行此操作", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=HTTP_403_FORBIDDEN,
            detail=detail,
        )


class Conflict(AppException):
    """资源冲突（如重复注册）"""

    def __init__(self, message: str = "资源冲突", detail: Optional[Any] = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=HTTP_409_CONFLICT,
            detail=detail,
        )


class RateLimited(AppException):
    """请求频率限制"""

    def __init__(self, message: str = "请求过于频繁，请稍后再试"):
        super().__init__(
            message=message,
            code="RATE_LIMITED",
            status_code=HTTP_429_TOO_MANY_REQUESTS,
        )


# ============================================================
# 全局异常处理器
# ============================================================

def register_exception_handlers(app):
    """在 FastAPI 应用上注册全局异常处理器

    Args:
        app: FastAPI 应用实例
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """处理自定义业务异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": exc.code or "APP_ERROR",
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """处理 Pydantic 数据验证错误"""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            })
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "code": "VALIDATION_ERROR",
                "message": "请求数据验证失败",
                "detail": errors,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """处理未捕获的异常（兜底）"""
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "detail": str(exc) if app.debug else None,
            },
        )
