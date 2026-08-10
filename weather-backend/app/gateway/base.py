"""天气查询平台 - 天气数据源适配器基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CurrentWeather:
    """实时天气统一模型"""

    temp: float
    feels_like: float
    temp_min: float
    temp_max: float
    humidity: int
    pressure: int
    wind_speed: float
    wind_deg: int
    wind_direction: str
    visibility: int | None
    clouds: int
    uv_index: float | None
    weather_id: int
    weather_main: str
    weather_description: str
    weather_icon: str
    sunrise: str | None
    sunset: str | None
    updated_at: str


@dataclass
class DailyForecast:
    """每日预报统一模型"""

    date: str
    temp_min: float
    temp_max: float
    temp_morn: float | None = None
    temp_day: float | None = None
    temp_eve: float | None = None
    temp_night: float | None = None
    feels_like_day: float | None = None
    feels_like_night: float | None = None
    humidity: int = 0
    wind_speed: float = 0.0
    wind_direction: str = ""
    weather_id: int = 800
    weather_main: str = "Clear"
    weather_description: str = ""
    weather_icon: str = "01d"
    rain_probability: float = 0.0
    snow_probability: float = 0.0
    sunrise: str | None = None
    sunset: str | None = None
    aqi: int | None = None


@dataclass
class HourlyForecast:
    """逐小时预报统一模型"""

    time: str
    temp: float
    feels_like: float
    humidity: int
    wind_speed: float
    wind_direction: str
    weather_id: int
    weather_main: str
    weather_description: str
    weather_icon: str
    rain_probability: float = 0.0


@dataclass
class AQIData:
    """空气质量统一模型"""

    aqi: int
    level: str  # 优/良/轻度污染/...
    primary_pollutant: str | None
    pm25: float | None
    pm10: float | None
    o3: float | None
    no2: float | None
    so2: float | None
    co: float | None


@dataclass
class WeatherAlert:
    """天气预警统一模型"""

    alert_id: str
    title: str
    description: str | None
    severity: str  # minor/moderate/severe/extreme
    event_type: str
    start_time: str
    end_time: str


class WeatherAdapter(ABC):
    """天气数据源适配器基类"""

    source_name: str = "unknown"

    @abstractmethod
    async def get_current(self, lat: float, lon: float, lang: str = "zh") -> CurrentWeather:
        """获取实时天气"""
        ...

    @abstractmethod
    async def get_hourly(self, lat: float, lon: float, hours: int = 48, lang: str = "zh") -> list[HourlyForecast]:
        """获取逐小时预报"""
        ...

    @abstractmethod
    async def get_daily(self, lat: float, lon: float, days: int = 7, lang: str = "zh") -> list[DailyForecast]:
        """获取逐日预报"""
        ...

    @abstractmethod
    async def get_aqi(self, lat: float, lon: float, lang: str = "zh") -> AQIData | None:
        """获取空气质量"""
        ...

    @abstractmethod
    async def get_alerts(self, lat: float, lon: float, lang: str = "zh") -> list[WeatherAlert]:
        """获取天气预警"""
        ...

    def _to_json(self, data: Any) -> dict:
        """将 dataclass 转为可 JSON 序列化的 dict"""
        if hasattr(data, "__dataclass_fields__"):
            result = {}
            for f_name in data.__dataclass_fields__:
                value = getattr(data, f_name)
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[f_name] = value
            return result
        return data
