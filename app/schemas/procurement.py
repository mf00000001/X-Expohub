"""采购需求相关 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProcurementCreate(BaseModel):
    """创建采购需求请求"""

    title: str = Field(..., min_length=2, max_length=200, description="采购标题")
    description: Optional[str] = Field(None, description="需求详细描述")
    category: str = Field(..., min_length=2, max_length=100, description="采购品类")
    budget_min: Optional[float] = Field(None, ge=0, description="预算下限")
    budget_max: Optional[float] = Field(None, ge=0, description="预算上限")
    deadline: Optional[str] = Field(None, description="采购截止日期")


class ProcurementUpdate(BaseModel):
    """更新采购需求请求"""

    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    deadline: Optional[str] = None
    status: Optional[str] = None


class ProcurementResponse(BaseModel):
    """采购需求响应"""

    id: int
    visitor_id: int
    visitor_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    deadline: Optional[datetime] = None
    status: str
    match_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MatchCreate(BaseModel):
    """创建采购匹配请求"""

    procurement_id: int = Field(..., description="采购需求ID")
    message: Optional[str] = Field(None, description="展商留言/报价说明")
    quoted_price: Optional[float] = Field(None, ge=0, description="报价")


class MatchResponse(BaseModel):
    """采购匹配响应"""

    id: int
    procurement_id: int
    exhibitor_id: int
    exhibitor_name: Optional[str] = None
    company_name: Optional[str] = None
    message: Optional[str] = None
    quoted_price: Optional[float] = None
    is_accepted: Optional[bool] = None
    created_at: datetime

    class Config:
        from_attributes = True
