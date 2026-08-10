"""消息相关 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    """发送消息请求"""

    receiver_id: int = Field(..., description="接收者用户ID")
    title: str = Field(..., min_length=1, max_length=200, description="消息标题")
    content: str = Field(..., min_length=1, description="消息内容")


class MessageResponse(BaseModel):
    """消息响应"""

    id: int
    sender_id: int
    sender_name: Optional[str] = None
    receiver_id: int
    receiver_name: Optional[str] = None
    title: str
    content: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListParams(BaseModel):
    """消息列表查询参数"""

    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    unread_only: bool = Field(False, description="仅查看未读")
