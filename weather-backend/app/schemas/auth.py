"""天气查询平台 - 认证相关 Pydantic 模型"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """用户注册请求"""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="用户名",
        examples=["zhangsan"],
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="密码（至少 6 位）",
    )
    email: Optional[str] = Field(
        None,
        max_length=255,
        description="邮箱（可选）",
        examples=["user@example.com"],
    )
    phone: Optional[str] = Field(
        None,
        max_length=20,
        description="手机号（可选）",
    )
    nickname: Optional[str] = Field(
        None,
        max_length=100,
        description="昵称（可选）",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v.strip().lower()


class LoginRequest(BaseModel):
    """用户登录请求"""

    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class UserResponse(BaseModel):
    """用户信息响应"""

    id: int
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    temp_unit: str = "celsius"
    lang: str = "zh-CN"
    status: str = "active"
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """登录/注册返回的 Token 响应"""

    access_token: str = Field(..., description="JWT Access Token")
    token_type: str = Field(default="bearer", description="Token 类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    user: UserResponse = Field(..., description="用户信息")


class AuthResponse(BaseModel):
    """统一认证响应"""

    code: int = 200
    data: TokenResponse | None = None
    message: str = "ok"
