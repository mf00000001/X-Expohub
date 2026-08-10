"""统一响应工具"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from app.schemas.common import ApiResponse

T = TypeVar("T")


def success(data: Optional[T] = None, message: str = "success") -> ApiResponse[T]:
    """
    成功响应

    Args:
        data: 响应数据
        message: 成功消息

    Returns:
        API 响应对象
    """
    return ApiResponse(code=200, message=message, data=data)


def created(data: Optional[T] = None, message: str = "创建成功") -> ApiResponse[T]:
    """
    创建成功响应

    Args:
        data: 响应数据
        message: 成功消息

    Returns:
        API 响应对象
    """
    return ApiResponse(code=201, message=message, data=data)


def error(code: int = 400, message: str = "请求失败", detail: Any = None) -> ApiResponse:
    """
    错误响应

    Args:
        code: 错误码
        message: 错误消息
        detail: 错误详情

    Returns:
        API 响应对象
    """
    return ApiResponse(code=code, message=message, data={"detail": detail} if detail else None)
