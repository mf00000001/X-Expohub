"""认证相关 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """注册请求体"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., pattern=r"^[\w.-]+@[\w.-]+\.\w+$", description="邮箱")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    role: str = Field(..., pattern=r"^(visitor|exhibitor|boss|organizer)$", description="用户角色")
    nickname: Optional[str] = Field(None, max_length=100, description="昵称")
    phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$", description="手机号")
    company: Optional[str] = Field(None, max_length=200, description="公司名称")
    code: str = Field(..., min_length=4, max_length=6, description="验证码")


class LoginRequest(BaseModel):
    """登录请求体"""

    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """令牌响应"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """刷新令牌请求"""

    refresh_token: str = Field(..., description="Refresh Token")


class UserInfoResponse(BaseModel):
    """登录后返回的用户信息"""

    id: int
    username: str
    email: str
    role: str
    status: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    company: Optional[str] = None


class LoginResponse(BaseModel):
    """登录响应"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfoResponse
