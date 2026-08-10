"""天气查询平台 - 认证服务（注册 / 登录 / JWT）"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException, UnauthorizedException
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User

logger = logging.getLogger("weather.auth")


class AuthService:
    """用户认证服务"""

    async def register(
        self,
        db: AsyncSession,
        username: str,
        password: str,
        email: str | None = None,
        phone: str | None = None,
        nickname: str | None = None,
    ) -> tuple[User, str]:
        """注册新用户

        Returns:
            (user, access_token)
        """
        # 检查用户名是否已存在
        existing = await db.execute(
            select(User).where(User.username == username)
        )
        if existing.scalar_one_or_none():
            raise AppException(
                message="用户名已被注册",
                status_code=409,
                detail=f"用户名 '{username}' 已被占用",
            )

        # 检查邮箱是否已存在
        if email:
            existing_email = await db.execute(
                select(User).where(User.email == email)
            )
            if existing_email.scalar_one_or_none():
                raise AppException(
                    message="邮箱已被注册",
                    status_code=409,
                    detail=f"邮箱 '{email}' 已被占用",
                )

        # 检查手机号是否已存在
        if phone:
            existing_phone = await db.execute(
                select(User).where(User.phone == phone)
            )
            if existing_phone.scalar_one_or_none():
                raise AppException(
                    message="手机号已被注册",
                    status_code=409,
                    detail=f"手机号 '{phone}' 已被占用",
                )

        # 创建用户
        user = User(
            username=username,
            email=email,
            phone=phone,
            nickname=nickname or username,
            password_hash=hash_password(password),
            temp_unit="celsius",
            lang="zh-CN",
            status="active",
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        # 生成 JWT
        token = create_access_token(user.id, user.username)

        logger.info(f"新用户注册: {username} (id={user.id})")
        return user, token

    async def login(
        self,
        db: AsyncSession,
        username: str,
        password: str,
    ) -> tuple[User, str]:
        """用户登录

        Returns:
            (user, access_token)

        Raises:
            UnauthorizedException: 用户名或密码错误
        """
        # 查找用户
        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise UnauthorizedException(
                message="用户名或密码错误",
                detail="用户不存在",
            )

        if user.status != "active":
            raise UnauthorizedException(
                message="账号已被禁用",
                detail=f"账号状态: {user.status}",
            )

        if not verify_password(password, user.password_hash):
            raise UnauthorizedException(
                message="用户名或密码错误",
                detail="密码不正确",
            )

        # 更新最后登录时间
        user.last_login_at = datetime.now(timezone.utc)
        await db.flush()

        # 生成 JWT
        token = create_access_token(user.id, user.username)

        logger.info(f"用户登录: {username} (id={user.id})")
        return user, token

    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> User | None:
        """根据 ID 获取用户"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    def verify_token(token: str) -> dict:
        """验证 JWT 并返回载荷"""
        return decode_token(token)

    @staticmethod
    def make_token(user_id: int, username: str) -> str:
        """生成 JWT（供外部使用）"""
        return create_access_token(user_id, username)


# 全局单例
auth_service = AuthService()
