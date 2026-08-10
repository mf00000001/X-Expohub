"""天气查询平台 - FastAPI 依赖注入"""

from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedException
from app.core.security import decode_token
from app.database.session import get_db
from app.models import User
from app.services.auth_service import auth_service


async def get_current_user(
    authorization: str = Header(..., description="Bearer <token>"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从 Authorization Header 中提取并验证 JWT，返回当前用户。

    用法:
        @router.get("/me")
        async def my_profile(current_user: User = Depends(get_current_user)):
            ...
    """
    if not authorization:
        raise UnauthorizedException(message="缺少认证令牌")

    # 支持 "Bearer <token>" 和直接 "<token>" 两种格式
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        raise UnauthorizedException(message="认证令牌不能为空")

    # 解码 JWT
    try:
        payload = decode_token(token)
    except ValueError as e:
        raise UnauthorizedException(message=str(e))

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException(message="无效的令牌载荷")

    # 获取用户
    user = await auth_service.get_user_by_id(db, int(user_id))
    if not user:
        raise UnauthorizedException(message="用户不存在或已被删除")

    if user.status != "active":
        raise UnauthorizedException(message="账号已被禁用")

    return user


async def get_current_user_id(
    current_user: User = Depends(get_current_user),
) -> int:
    """
    从当前认证用户中提取用户 ID（便捷依赖）。

    用法:
        @router.get("/favorites")
        async def my_favorites(user_id: int = Depends(get_current_user_id)):
            ...
    """
    return current_user.id


async def get_optional_user(
    authorization: str | None = Header(None, description="可选的 Bearer <token>"),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    可选的用户认证：有 token 则返回用户，无 token 返回 None。

    适用于既允许匿名访问又希望识别登录用户的接口。
    """
    if not authorization:
        return None

    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]

    if not token:
        return None

    try:
        payload = decode_token(token)
    except ValueError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = await auth_service.get_user_by_id(db, int(user_id))
    if not user or user.status != "active":
        return None

    return user
