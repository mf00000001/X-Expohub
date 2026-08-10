"""分页工具"""

from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from app.schemas.common import PaginatedResponse

T = TypeVar("T")


def paginate(
    items: Sequence[Any],
    total: int,
    page: int,
    page_size: int,
) -> PaginatedResponse:
    """
    创建分页响应

    Args:
        items: 数据项列表
        total: 总数
        page: 当前页码
        page_size: 每页数量

    Returns:
        分页响应对象
    """
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=list(items),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
