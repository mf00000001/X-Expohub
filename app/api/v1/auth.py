"""认证 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_auth
from app.database.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserInfoResponse,
)
from app.schemas.common import ApiResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=ApiResponse[LoginResponse], status_code=201)
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """
    用户注册

    - 选择角色注册（visitor/exhibitor/boss/organizer）
    - 验证码校验（模拟）
    - 返回令牌对 + 用户信息
    """
    result = auth_service.register(
        db=db,
        username=data.username,
        email=data.email,
        password=data.password,
        role=data.role,
        nickname=data.nickname,
        phone=data.phone,
        company=data.company,
        code=data.code,
    )
    return ApiResponse(data=LoginResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type="bearer",
        expires_in=result["expires_in"],
        user=UserInfoResponse(**result["user"]),
    ))


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    用户登录

    - 支持用户名或邮箱登录
    - 返回 access_token + refresh_token
    - 返回用户基本信息
    """
    result = auth_service.login(db=db, username=data.username, password=data.password)
    return ApiResponse(data=LoginResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type="bearer",
        expires_in=result["expires_in"],
        user=UserInfoResponse(**result["user"]),
    ))


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh_token(data: RefreshRequest):
    """
    刷新 Access Token

    - 使用 Refresh Token 获取新的令牌对
    - Refresh Token 有效期7天
    """
    result = auth_service.refresh_token(data.refresh_token)
    return ApiResponse(data=TokenResponse(**result))


@router.post("/logout", response_model=ApiResponse)
async def logout(current_user=Depends(require_auth)):
    """
    用户登出

    - 将当前 Access Token 加入黑名单
    - 需要登录
    """
    token = current_user.token_payload
    # 实际登出逻辑在中间件处理
    return ApiResponse(message="已登出")


@router.get("/me", response_model=ApiResponse[UserInfoResponse])
async def get_current_user_info(current_user=Depends(require_auth)):
    """获取当前登录用户信息"""
    return ApiResponse(data=UserInfoResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        status=current_user.user.status,
        nickname=current_user.user.nickname,
        avatar_url=current_user.user.avatar_url,
        company=current_user.user.company,
    ))
