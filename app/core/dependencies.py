"""依赖注入：认证、角色、权限检查（异步版）"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.permissions import Permission, Role, check_permission
from app.core.security import decode_token
from app.database.session import get_db
from app.models.user import User

# HTTP Bearer 认证方案
bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """当前认证用户信息"""

    def __init__(self, user: User, token_payload: dict[str, Any]):
        self.user = user
        self.id = user.id
        self.role = user.role
        self.username = user.username
        self.email = user.email
        self.token_payload = token_payload


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """
    获取当前登录用户（依赖注入）

    Args:
        credentials: HTTP Bearer 认证凭据
        db: 异步数据库会话

    Returns:
        当前用户信息

    Raises:
        HTTPException 401: 未登录或令牌无效
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查令牌类型
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型错误，请使用 Access Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload.get("sub", 0))
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"账号状态异常: {user.status}",
        )

    return CurrentUser(user=user, token_payload=payload)


async def require_auth(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    要求用户已登录（任意角色）
    """
    return current_user


def require_role(*roles: Role):
    """
    要求用户拥有指定角色之一
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in [r.value for r in roles]:
            raise ForbiddenException(
                message=f"需要角色 {'/'.join(r.value for r in roles)}",
            )
        return current_user
    return role_checker


def require_permission(permission: Permission):
    """
    要求用户拥有指定权限
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        role = Role(current_user.role)
        if not check_permission(role, permission):
            raise ForbiddenException(
                message=f"权限不足，需要 {permission.value}",
            )
        return current_user
    return permission_checker


# 快捷角色依赖
require_visitor = require_role(Role.VISITOR)
require_exhibitor = require_role(Role.EXHIBITOR)
require_organizer = require_role(Role.ORGANIZER)
require_boss = require_role(Role.BOSS)
require_staff = require_role(Role.ORGANIZER, Role.BOSS)
require_any_user = require_role(Role.VISITOR, Role.EXHIBITOR, Role.ORGANIZER, Role.BOSS)
