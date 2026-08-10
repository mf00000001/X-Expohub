"""天气查询平台 - Pydantic 请求/响应模型"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 实时天气
# ──────────────────────────────────────────────

class CurrentWeatherResponse(BaseModel):
    """实时天气响应"""
    temperature: float = Field(..., description="当前温度 (℃)")
    feels_like: float = Field(..., description="体感温度 (℃)")
    humidity: int = Field(..., description="相对湿度 (%)")
    wind_speed: float = Field(..., description="风速 (km/h)")
    wind_dir: str = Field(..., description="风向描述")
    description: str = Field(..., description="天气描述")
    icon: str = Field(..., description="天气图标代码")
    update_time: Optional[str] = Field(None, description="数据更新时间")


# ──────────────────────────────────────────────
# 天气预报
# ──────────────────────────────────────────────

class ForecastDay(BaseModel):
    """单日预报"""
    date: str = Field(..., description="日期 (yyyy-MM-dd)")
    high_temp: float = Field(..., description="最高温度 (℃)")
    low_temp: float = Field(..., description="最低温度 (℃)")
    description: str = Field(..., description="天气描述")
    icon: str = Field(..., description="天气图标代码")
    humidity: int = Field(..., description="相对湿度 (%)")
    wind_speed: float = Field(..., description="风速 (km/h)")


class ForecastResponse(BaseModel):
    """多日预报响应"""
    city_name: str = Field(..., description="城市名称")
    forecast_days: list[ForecastDay] = Field(default_factory=list, description="每日预报列表")


# ──────────────────────────────────────────────
# 空气质量 (AQI)
# ──────────────────────────────────────────────

class AQIResponse(BaseModel):
    """空气质量响应"""
    aqi: int = Field(..., description="空气质量指数")
    level: str = Field(..., description="空气质量等级 (优/良/轻度污染/...)")
    pm2_5: Optional[float] = Field(None, description="PM2.5 (μg/m³)")
    pm10: Optional[float] = Field(None, description="PM10 (μg/m³)")
    so2: Optional[float] = Field(None, description="SO₂ (μg/m³)")
    no2: Optional[float] = Field(None, description="NO₂ (μg/m³)")
    o3: Optional[float] = Field(None, description="O₃ (μg/m³)")
    co: Optional[float] = Field(None, description="CO (mg/m³)")
    primary_pollutant: Optional[str] = Field(None, description="首要污染物")


# ──────────────────────────────────────────────
# 城市搜索
# ──────────────────────────────────────────────

class CitySearchResult(BaseModel):
    """城市搜索结果"""
    city_id: str = Field(..., description="外部 API 城市 ID")
    name: str = Field(..., description="城市名称")
    province: Optional[str] = Field(None, description="省份/州")
    lat: float = Field(..., description="纬度")
    lon: float = Field(..., description="经度")


# ──────────────────────────────────────────────
# 收藏
# ──────────────────────────────────────────────

class FavoriteCreate(BaseModel):
    """创建收藏请求"""
    city_id: str = Field(..., description="外部 API 城市 ID")


class FavoriteResponse(BaseModel):
    """收藏响应"""
    id: int = Field(..., description="收藏记录 ID")
    user_id: int = Field(..., description="用户 ID")
    city_id: int = Field(..., description="数据库城市 ID")
    city_name: Optional[str] = Field(None, description="城市名称")
    created_at: Optional[datetime] = Field(None, description="创建时间")


# ──────────────────────────────────────────────
# 通用
# ──────────────────────────────────────────────

class WeatherQueryParams(BaseModel):
    """天气查询通用参数"""
    city_id: Optional[str] = Field(None, description="外部 API 城市 ID")
    lat: Optional[float] = Field(None, ge=-90, le=90, description="纬度")
    lon: Optional[float] = Field(None, ge=-180, le=180, description="经度")
    lang: str = Field("zh", description="语言")
