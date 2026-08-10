"""天气查询平台 - 认证 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import auth_service
from app.utils.response import success_response

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", summary="用户注册")
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    注册新用户

    - **username**: 用户名（3-50 字符，字母/数字/下划线/连字符）
    - **password**: 密码（至少 6 位）
    - **email**: 邮箱（可选）
    - **phone**: 手机号（可选）
    - **nickname**: 昵称（可选，默认与用户名相同）
    """
    user, token = await auth_service.register(
        db=db,
        username=body.username,
        password=body.password,
        email=body.email,
        phone=body.phone,
        nickname=body.nickname,
    )

    token_data = TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )

    return success_response(
        data=token_data.model_dump(),
        message="注册成功",
    )


@router.post("/login", summary="用户登录")
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录

    - **username**: 用户名
    - **password**: 密码
    """
    user, token = await auth_service.login(
        db=db,
        username=body.username,
        password=body.password,
    )

    token_data = TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )

    return success_response(
        data=token_data.model_dump(),
        message="登录成功",
    )
