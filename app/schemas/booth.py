"""展位相关 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BoothCreate(BaseModel):
    """创建展位请求"""

    exhibition_id: int = Field(..., description="所属展会ID")
    booth_number: str = Field(..., min_length=1, max_length=50, description="展位编号")
    name: Optional[str] = Field(None, max_length=200, description="展位名称")
    description: Optional[str] = Field(None, description="展位描述")
    area: Optional[float] = Field(None, ge=0, description="展位面积（㎡）")
    price: Optional[float] = Field(None, ge=0, description="展位价格")
    floor: Optional[int] = Field(None, description="楼层")
    zone: Optional[str] = Field(None, max_length=50, description="展区")


class BoothUpdate(BaseModel):
    """更新展位请求"""

    name: Optional[str] = None
    description: Optional[str] = None
    area: Optional[float] = None
    price: Optional[float] = None
    status: Optional[str] = None
    exhibitor_id: Optional[int] = None


class BoothResponse(BaseModel):
    """展位响应"""

    id: int
    exhibition_id: int
    exhibition_name: Optional[str] = None
    exhibitor_id: Optional[int] = None
    exhibitor_name: Optional[str] = None
    booth_number: str
    name: Optional[str] = None
    description: Optional[str] = None
    area: Optional[float] = None
    price: Optional[float] = None
    floor: Optional[int] = None
    zone: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BoothBookRequest(BaseModel):
    """预订展位请求"""

    booth_id: int = Field(..., description="展位ID")
