"""天气查询平台 - 自定义异常类"""

from __future__ import annotations


class AppException(Exception):
    """应用基础异常"""

    def __init__(self, message: str, status_code: int = 400, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class NotFoundException(AppException):
    """资源未找到"""

    def __init__(self, message: str = "资源未找到", detail: str | None = None):
        super().__init__(message, status_code=404, detail=detail)


class UnauthorizedException(AppException):
    """未认证"""

    def __init__(self, message: str = "请先登录", detail: str | None = None):
        super().__init__(message, status_code=401, detail=detail)


class ForbiddenException(AppException):
    """无权限"""

    def __init__(self, message: str = "无权限访问", detail: str | None = None):
        super().__init__(message, status_code=403, detail=detail)


class RateLimitException(AppException):
    """请求限流"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="请求过于频繁，请稍后再试",
            status_code=429,
            detail=f"请在 {retry_after} 秒后重试",
        )
        self.retry_after = retry_after


class ExternalApiException(AppException):
    """外部 API 调用失败"""

    def __init__(self, source: str, detail: str = ""):
        super().__init__(
            message=f"天气数据源 {source} 暂不可用",
            status_code=502,
            detail=detail,
        )


class ValidationException(AppException):
    """参数校验失败"""

    def __init__(self, message: str = "参数错误", detail: str | None = None):
        super().__init__(message, status_code=422, detail=detail)
