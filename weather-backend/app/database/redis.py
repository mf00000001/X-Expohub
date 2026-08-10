"""天气查询平台 - Redis 连接管理 (SQLite 版本，已禁用)"""

from __future__ import annotations


async def get_redis():
    """Redis 已禁用，返回 None"""
    return None


async def close_redis() -> None:
    """Redis 已禁用"""
    pass
