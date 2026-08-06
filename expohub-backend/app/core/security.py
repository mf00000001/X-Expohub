"""
JWT 双令牌认证 + 密码加密模块

提供：
- create_access_token / create_refresh_token：生成双令牌
- verify_token：解码验证 JWT
- hash_password / verify_password：密码加密与校验
- TokenBlacklist：Redis 黑名单管理（已撤销令牌）
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ============================================================
# 密码加密（bcrypt）
# ============================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希

    Args:
        password: 明文密码

    Returns:
        bcrypt 哈希后的密码字符串
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希密码是否匹配

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        匹配返回 True，否则 False
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# JWT 令牌生成与验证
# ============================================================

def _create_token(
    data: dict[str, Any],
    expires_delta: timedelta,
    token_type: str,
) -> str:
    """创建 JWT 令牌（内部方法）

    Args:
        data: 载荷数据（需包含 sub=用户ID, role=角色）
        expires_delta: 过期时间增量
        token_type: 令牌类型（access / refresh）

    Returns:
        编码后的 JWT 字符串
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())

    payload = {
        "sub": str(data.get("sub")),
        "role": data.get("role"),
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": now + expires_delta,
    }
    # 保留额外自定义字段
    for key, value in data.items():
        if key not in payload:
            payload[key] = value

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """创建 Access Token（短期令牌，默认 15 分钟）

    Args:
        data: 载荷数据，必须包含 sub(用户ID) 和 role
        expires_delta: 自定义过期时间，默认 15 分钟

    Returns:
        JWT access token 字符串
    """
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(data, delta, token_type="access")


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """创建 Refresh Token（长期令牌，默认 7 天）

    Args:
        data: 载荷数据，必须包含 sub(用户ID) 和 role
        expires_delta: 自定义过期时间，默认 7 天

    Returns:
        JWT refresh token 字符串
    """
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(data, delta, token_type="refresh")


def verify_token(token: str) -> dict[str, Any]:
    """解码并验证 JWT 令牌

    Args:
        token: JWT 字符串

    Returns:
        解码后的 payload 字典

    Raises:
        ValueError: 令牌无效、过期或签名错误
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise ValueError(f"无效的令牌: {exc}") from exc


# ============================================================
# Token 黑名单管理（Redis）
# ============================================================

class TokenBlacklist:
    """JWT 令牌黑名单管理器

    使用 Redis 存储已撤销的令牌 jti，支持自动过期淘汰。
    需在应用启动时通过 init_redis 初始化 Redis 连接。
    """

    _redis = None  # Redis 连接实例（延迟初始化）

    @classmethod
    async def init_redis(cls, redis_client) -> None:
        """初始化 Redis 连接

        Args:
            redis_client: Redis 异步客户端实例
        """
        cls._redis = redis_client

    @classmethod
    async def add_to_blacklist(cls, jti: str, expires_in: int) -> None:
        """将令牌加入黑名单

        Args:
            jti: 令牌唯一 ID
            expires_in: 过期时间（秒），与令牌剩余有效期一致
        """
        if cls._redis is None:
            return  # Redis 未就绪时静默忽略
        await cls._redis.setex(f"token_blacklist:{jti}", expires_in, "revoked")

    @classmethod
    async def is_blacklisted(cls, jti: str) -> bool:
        """检查令牌是否在黑名单中

        Args:
            jti: 令牌唯一 ID

        Returns:
            在黑名单中返回 True，否则 False
        """
        if cls._redis is None:
            return False
        result = await cls._redis.get(f"token_blacklist:{jti}")
        return result is not None

    @classmethod
    async def remove_from_blacklist(cls, jti: str) -> None:
        """从黑名单中移除令牌（通常用于测试）

        Args:
            jti: 令牌唯一 ID
        """
        if cls._redis is not None:
            await cls._redis.delete(f"token_blacklist:{jti}")
