"""通用响应体 Schema"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""

    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class PaginationParams(BaseModel):
    """分页查询参数"""

    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应格式"""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class ErrorResponse(BaseModel):
    """错误响应"""

    code: int
    message: str
    detail: Optional[Any] = None
