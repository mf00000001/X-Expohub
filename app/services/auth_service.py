"""认证服务：注册、登录、令牌刷新（异步版）"""

from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from typing import Any, Optional

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BusinessException,
    ConflictException,
    UnauthorizedException,
)
from app.core.security import (
    create_token_pair,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database.redis import get_redis
from app.models.user import User


def _generate_verification_code() -> str:
    """生成6位数字验证码"""
    return "".join(random.choices(string.digits, k=6))


def send_verification_code(email: str) -> str:
    """
    发送验证码（模拟）

    Args:
        email: 目标邮箱

    Returns:
        验证码
    """
    code = _generate_verification_code()
    # TODO: 集成真实邮件服务
    print(f"[模拟] 验证码已发送至 {email}: {code}")
    return code


async def register(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    role: str,
    nickname: Optional[str] = None,
    phone: Optional[str] = None,
    company: Optional[str] = None,
    code: Optional[str] = None,
) -> dict[str, Any]:
    """
    用户注册

    Args:
        db: 异步数据库会话
        username: 用户名
        email: 邮箱
        password: 明文密码
        role: 用户角色
        nickname: 昵称
        phone: 手机号
        company: 公司名称
        code: 验证码

    Returns:
        令牌对 + 用户信息

    Raises:
        ConflictException: 用户名或邮箱已存在
        BusinessException: 验证码错误
    """
    # 检查重复
    result = await db.execute(
        select(User).where((User.username == username) | (User.email == email))
    )
    existing = result.scalars().first()
    if existing:
        if existing.username == username:
            raise ConflictException("用户名已存在")
        raise ConflictException("邮箱已存在")

    # 验证码校验（模拟）
    if code:
        # TODO: 集成真实验证码校验
        pass

    # 创建用户
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role,
        nickname=nickname or username,
        phone=phone,
        company=company,
        status="active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 生成令牌
    tokens = create_token_pair(user.id, user.role)

    return {
        **tokens,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "company": user.company,
        },
    }


async def login(db: AsyncSession, username: str, password: str) -> dict[str, Any]:
    """
    用户登录

    Args:
        db: 异步数据库会话
        username: 用户名或邮箱
        password: 明文密码

    Returns:
        令牌对 + 用户信息

    Raises:
        UnauthorizedException: 账号或密码错误
        BusinessException: 账号状态异常
    """
    # 支持用户名或邮箱登录
    result = await db.execute(
        select(User).where(
            (User.username == username) | (User.email == username),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalars().first()

    if user is None:
        raise UnauthorizedException("账号或密码错误")

    if not verify_password(password, user.password_hash):
        raise UnauthorizedException("账号或密码错误")

    if user.status != "active":
        raise BusinessException(f"账号状态异常: {user.status}")

    # 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # 生成令牌
    tokens = create_token_pair(user.id, user.role)

    return {
        **tokens,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "company": user.company,
        },
    }


def refresh_token(refresh_token_str: str) -> dict[str, Any]:
    """
    刷新 Access Token（无需数据库）

    Args:
        refresh_token_str: Refresh Token 字符串

    Returns:
        新的令牌对

    Raises:
        UnauthorizedException: Refresh Token 无效或已过期
    """
    try:
        payload = decode_token(refresh_token_str)
    except JWTError:
        raise UnauthorizedException("Refresh Token 无效或已过期")

    # 检查令牌类型
    if payload.get("type") != "refresh":
        raise UnauthorizedException("令牌类型错误")

    user_id = int(payload.get("sub", 0))
    role = payload.get("role", "")

    # 生成新的令牌对
    return create_token_pair(user_id, role)


async def logout(token: str) -> None:
    """
    用户登出（将令牌加入黑名单）

    Args:
        token: Access Token
    """
    if not settings.TOKEN_BLACKLIST_ENABLED:
        return

    try:
        payload = decode_token(token)
    except JWTError:
        return

    exp = payload.get("exp", 0)
    now = datetime.now(timezone.utc).timestamp()

    # 计算剩余有效期
    ttl = int(exp - now)
    if ttl <= 0:
        return

    # 加入黑名单
    redis = get_redis()
    jti = payload.get("jti", f"token:{payload.get('sub')}:{payload.get('iat')}")
    redis.setex(
        f"{settings.TOKEN_BLACKLIST_PREFIX}{jti}",
        ttl,
        "revoked",
    )
