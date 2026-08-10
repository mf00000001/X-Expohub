"""团队相关 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    """创建团队请求"""

    name: str = Field(..., min_length=2, max_length=100, description="团队名称")
    description: Optional[str] = Field(None, max_length=500, description="团队描述")


class TeamUpdate(BaseModel):
    """更新团队请求"""

    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None


class TeamMemberAdd(BaseModel):
    """添加团队成员请求"""

    user_id: int = Field(..., description="成员用户ID")
    role_in_team: str = Field("member", pattern=r"^(admin|member)$", description="团队内角色")


class TeamMemberResponse(BaseModel):
    """团队成员响应"""

    id: int
    team_id: int
    user_id: int
    username: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    role_in_team: str
    joined_at: datetime

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    """团队响应"""

    id: int
    boss_id: int
    boss_name: Optional[str] = None
    name: str
    description: Optional[str] = None
    member_count: int = 0
    members: list[TeamMemberResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
