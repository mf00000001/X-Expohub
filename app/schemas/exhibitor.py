"""展商相关 Schema"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExhibitorCreate(BaseModel):
    """创建展商信息请求"""

    company_name: str = Field(..., min_length=2, max_length=200, description="公司全称")
    company_short_name: Optional[str] = Field(None, max_length=50, description="公司简称")
    logo_url: Optional[str] = Field(None, max_length=500, description="公司Logo")
    business_scope: Optional[str] = Field(None, description="经营范围")
    website: Optional[str] = Field(None, max_length=200, description="公司官网")
    contact_name: Optional[str] = Field(None, max_length=50, description="联系人姓名")
    contact_phone: Optional[str] = Field(None, max_length=20, description="联系人电话")
    contact_email: Optional[str] = Field(None, max_length=255, description="联系人邮箱")


class ExhibitorUpdate(BaseModel):
    """更新展商信息请求"""

    company_name: Optional[str] = Field(None, min_length=2, max_length=200)
    company_short_name: Optional[str] = None
    logo_url: Optional[str] = None
    business_scope: Optional[str] = None
    website: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


class ExhibitorResponse(BaseModel):
    """展商信息响应"""

    id: int
    user_id: int
    company_name: str
    company_short_name: Optional[str] = None
    logo_url: Optional[str] = None
    business_scope: Optional[str] = None
    website: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    status: str
    verified_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    """创建展品请求"""

    name: str = Field(..., min_length=2, max_length=200, description="展品名称")
    description: Optional[str] = Field(None, description="展品描述")
    category: str = Field(..., min_length=2, max_length=100, description="展品类目")
    images: Optional[str] = Field(None, description="图片URL列表（JSON数组）")
    price: Optional[float] = Field(None, ge=0, description="展品价格")
    specs: Optional[str] = Field(None, description="规格参数（JSON字符串）")
    booth_id: Optional[int] = Field(None, description="所属展位ID")
    exhibition_id: Optional[int] = Field(None, description="所属展会ID")


class ProductUpdate(BaseModel):
    """更新展品请求"""

    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    images: Optional[str] = None
    price: Optional[float] = None
    specs: Optional[str] = None
    status: Optional[str] = None


class ProductResponse(BaseModel):
    """展品响应"""

    id: int
    exhibitor_id: int
    booth_id: Optional[int] = None
    exhibition_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    category: str
    images: Optional[str] = None
    price: Optional[float] = None
    specs: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
