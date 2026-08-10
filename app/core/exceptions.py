"""自定义异常类"""

from __future__ import annotations

from typing import Any, Optional


class AppException(Exception):
    """应用基础异常"""

    def __init__(
        self,
        status_code: int = 500,
        code: str = "internal_error",
        message: str = "服务器内部错误",
        detail: Optional[Any] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class NotFoundException(AppException):
    """资源未找到"""

    def __init__(self, message: str = "资源不存在", detail: Optional[Any] = None):
        super().__init__(
            status_code=404,
            code="not_found",
            message=message,
            detail=detail,
        )


class UnauthorizedException(AppException):
    """未授权"""

    def __init__(self, message: str = "未登录或登录已过期", detail: Optional[Any] = None):
        super().__init__(
            status_code=401,
            code="unauthorized",
            message=message,
            detail=detail,
        )


class ForbiddenException(AppException):
    """权限不足"""

    def __init__(self, message: str = "权限不足，无法操作", detail: Optional[Any] = None):
        super().__init__(
            status_code=403,
            code="forbidden",
            message=message,
            detail=detail,
        )


class ConflictException(AppException):
    """资源冲突"""

    def __init__(self, message: str = "资源已存在", detail: Optional[Any] = None):
        super().__init__(
            status_code=409,
            code="conflict",
            message=message,
            detail=detail,
        )


class ValidationException(AppException):
    """数据验证失败"""

    def __init__(self, message: str = "数据验证失败", detail: Optional[Any] = None):
        super().__init__(
            status_code=422,
            code="validation_error",
            message=message,
            detail=detail,
        )


class BusinessException(AppException):
    """业务逻辑异常"""

    def __init__(self, message: str = "业务操作失败", code: str = "business_error", detail: Optional[Any] = None):
        super().__init__(
            status_code=400,
            code=code,
            message=message,
            detail=detail,
        )
