"""展会相关 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExhibitionCreate(BaseModel):
    """创建展会请求"""

    name: str = Field(..., min_length=2, max_length=200, description="展会名称")
    short_name: Optional[str] = Field(None, max_length=50, description="展会简称")
    description: Optional[str] = Field(None, description="展会描述")
    cover_url: Optional[str] = Field(None, max_length=500, description="封面图URL")
    start_date: str = Field(..., description="开始时间 (ISO 8601)")
    end_date: str = Field(..., description="结束时间 (ISO 8601)")
    registration_deadline: Optional[str] = Field(None, description="报名截止时间")
    venue: str = Field(..., min_length=2, max_length=200, description="举办场馆")
    address: str = Field(..., min_length=2, max_length=500, description="详细地址")
    city: str = Field(..., min_length=2, max_length=100, description="城市")
    total_booths: int = Field(0, ge=0, description="总展位数")


class ExhibitionUpdate(BaseModel):
    """更新展会请求"""

    name: Optional[str] = Field(None, min_length=2, max_length=200)
    short_name: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    cover_url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    registration_deadline: Optional[str] = None
    venue: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    total_booths: Optional[int] = None


class ExhibitionResponse(BaseModel):
    """展会响应体"""

    id: int
    name: str
    short_name: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    start_date: datetime
    end_date: datetime
    registration_deadline: Optional[datetime] = None
    venue: str
    address: str
    city: str
    status: str
    organizer_id: int
    organizer_name: Optional[str] = None
    total_booths: int = 0
    available_booths: int = 0
    visitor_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExhibitionListParams(BaseModel):
    """展会列表查询参数"""

    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    city: Optional[str] = Field(None, description="城市筛选")
    status: Optional[str] = Field(None, description="状态筛选")
    keyword: Optional[str] = Field(None, description="关键词搜索")
