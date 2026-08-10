"""用户相关 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserProfileUpdate(BaseModel):
    """用户资料更新请求"""

    nickname: Optional[str] = Field(None, max_length=100, description="昵称")
    avatar_url: Optional[str] = Field(None, max_length=500, description="头像URL")
    gender: Optional[str] = Field(None, pattern=r"^(male|female|other|secret)$", description="性别")
    company: Optional[str] = Field(None, max_length=200, description="公司名称")
    position: Optional[str] = Field(None, max_length=100, description="职位")
    bio: Optional[str] = Field(None, max_length=500, description="个人简介")
    phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$", description="手机号")


class UserResponse(BaseModel):
    """用户响应体"""

    id: int
    username: str
    email: str
    role: str
    status: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserSimpleResponse(BaseModel):
    """用户简要信息"""

    id: int
    username: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    company: Optional[str] = None
