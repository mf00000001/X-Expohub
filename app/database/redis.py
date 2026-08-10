"""Redis 连接管理"""

from __future__ import annotations

from typing import Optional

import redis.asyncio as aioredis
from redis import Redis

from app.core.config import settings

# 同步 Redis 客户端
redis_client: Optional[Redis] = None

# 异步 Redis 客户端
async_redis_client: Optional[aioredis.Redis] = None


def get_redis() -> Redis:
    """
    获取同步 Redis 客户端

    Returns:
        Redis 客户端实例
    """
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return redis_client


async def get_async_redis() -> aioredis.Redis:
    """
    获取异步 Redis 客户端

    Returns:
        异步 Redis 客户端实例
    """
    global async_redis_client
    if async_redis_client is None:
        async_redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return async_redis_client


def close_redis() -> None:
    """关闭同步 Redis 连接"""
    global redis_client
    if redis_client:
        redis_client.close()
        redis_client = None


async def close_async_redis() -> None:
    """关闭异步 Redis 连接"""
    global async_redis_client
    if async_redis_client:
        await async_redis_client.close()
        async_redis_client = None
