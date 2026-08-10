"""安全核心：JWT令牌管理、密码哈希"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    对密码进行 bcrypt 哈希

    Args:
        password: 明文密码

    Returns:
        哈希后的密码字符串
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否匹配

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: int,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建 Access Token（短期，默认15分钟）

    Args:
        user_id: 用户ID
        role: 用户角色
        expires_delta: 过期时间差，默认15分钟

    Returns:
        JWT access token 字符串
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: int,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建 Refresh Token（长期，默认7天）

    Args:
        user_id: 用户ID
        role: 用户角色
        expires_delta: 过期时间差，默认7天

    Returns:
        JWT refresh token 字符串
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "refresh",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_token_pair(user_id: int, role: str) -> dict[str, Any]:
    """
    创建令牌对（Access + Refresh）

    Args:
        user_id: 用户ID
        role: 用户角色

    Returns:
        包含 access_token, refresh_token, token_type, expires_in 的字典
    """
    access_token = create_access_token(user_id, role)
    refresh_token = create_refresh_token(user_id, role)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def decode_token(token: str) -> dict[str, Any]:
    """
    解码并验证 JWT Token

    Args:
        token: JWT 字符串

    Returns:
        解码后的 payload 字典

    Raises:
        JWTError: 令牌无效或已过期
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        raise


def get_token_payload(token: str) -> dict[str, Any]:
    """
    获取令牌载荷（不验证过期）

    Args:
        token: JWT 字符串

    Returns:
        解码后的 payload 字典
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_exp": False},
    )
