"""天气查询平台 - 天气服务（多源聚合 + 缓存）"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.exceptions import ExternalApiException, NotFoundException
from app.database.redis import get_redis
from app.gateway.base import AQIData, CurrentWeather, DailyForecast, HourlyForecast, WeatherAlert
from app.gateway.wttr_adapter import WttrAdapter
from app.gateway.qweather_adapter import QWeatherAdapter
from app.gateway.openweather_adapter import OpenWeatherAdapter

logger = logging.getLogger("weather")


class WeatherService:
    """天气数据服务：多源聚合 + 多级缓存"""

    def __init__(self):
        self.primary = WttrAdapter()          # wttr.in 免费，无需 API Key
        self.fallback = QWeatherAdapter()     # 和风天气（需 API Key）
        self.third = OpenWeatherAdapter()     # OpenWeather（需 API Key）

    # ── 缓存工具 ──

    async def _cache_get(self, key: str) -> dict | None:
        try:
            redis = await get_redis()
            data = await redis.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def _cache_set(self, key: str, data: dict, ttl: int) -> None:
        try:
            redis = await get_redis()
            await redis.setex(key, ttl, json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    def _cache_key(self, city_id: int, data_type: str) -> str:
        return f"weather:{data_type}:{city_id}"

    # ── 多源调用 ──

    async def _call_with_fallback(self, method: str, lat: float, lon: float, lang: str, **kwargs):
        """调用主数据源，失败则逐级降级"""
        for adapter in [self.primary, self.fallback, self.third]:
            fn = getattr(adapter, method, None)
            if fn is None:
                continue
            try:
                return await fn(lat=lat, lon=lon, lang=lang, **kwargs)
            except Exception as e:
                logger.warning(f"数据源 ({adapter.source_name}) {method} 失败: {e}")
                continue
        raise ExternalApiException(source="all", detail="所有天气数据源均不可用")

    # ── 公共接口 ──

    async def get_current(self, city_id: int, lat: float, lon: float, lang: str = "zh") -> dict:
        """获取实时天气（带缓存）"""
        cache_key = self._cache_key(city_id, "current")
        cached = await self._cache_get(cache_key)
        if cached:
            return cached

        weather: CurrentWeather = await self._call_with_fallback(
            "get_current", lat, lon, lang
        )
        result = weather.__dict__ if hasattr(weather, "__dict__") else self._serialize(weather)  # type: ignore[assignment]
        await self._cache_set(cache_key, result, settings.WEATHER_CACHE_TTL_CURRENT)
        return result

    async def get_hourly(self, city_id: int, lat: float, lon: float, lang: str = "zh", hours: int = 24) -> list[dict]:
        """获取逐小时预报"""
        cache_key = self._cache_key(city_id, "hourly")
        cached = await self._cache_get(cache_key)
        if cached:
            return cached

        forecasts: list[HourlyForecast] = await self._call_with_fallback(
            "get_hourly", lat, lon, lang, hours=hours
        )
        result = [self._serialize(f) for f in forecasts]
        await self._cache_set(cache_key, result, settings.WEATHER_CACHE_TTL_HOURLY)
        return result

    async def get_daily(self, city_id: int, lat: float, lon: float, lang: str = "zh", days: int = 7) -> list[dict]:
        """获取逐日预报"""
        cache_key = self._cache_key(city_id, "daily")
        cached = await self._cache_get(cache_key)
        if cached:
            return cached

        forecasts: list[DailyForecast] = await self._call_with_fallback(
            "get_daily", lat, lon, lang, days=days
        )
        result = [self._serialize(f) for f in forecasts]
        await self._cache_set(cache_key, result, settings.WEATHER_CACHE_TTL_DAILY)
        return result

    async def get_aqi(self, city_id: int, lat: float, lon: float, lang: str = "zh") -> dict | None:
        """获取空气质量"""
        cache_key = self._cache_key(city_id, "aqi")
        cached = await self._cache_get(cache_key)
        if cached:
            return cached if cached.get("aqi") else None

        aqi: AQIData | None = await self._call_with_fallback(
            "get_aqi", lat, lon, lang
        )
        if aqi is None:
            return None
        result = self._serialize(aqi)
        await self._cache_set(cache_key, result, settings.WEATHER_CACHE_TTL_AQI)
        return result

    async def get_alerts(self, city_id: int, lat: float, lon: float, lang: str = "zh") -> list[dict]:
        """获取天气预警"""
        cache_key = self._cache_key(city_id, "alerts")
        cached = await self._cache_get(cache_key)
        if cached:
            return cached

        alerts: list[WeatherAlert] = await self._call_with_fallback(
            "get_alerts", lat, lon, lang
        )
        result = [self._serialize(a) for a in alerts]
        await self._cache_set(cache_key, result, settings.WEATHER_CACHE_TTL_ALERTS)
        return result

    async def get_full_weather(self, city_id: int, lat: float, lon: float, lang: str = "zh", days: int = 7):
        """一次性获取完整天气数据"""
        import asyncio
        current, hourly, daily, aqi, alerts = await asyncio.gather(
            self.get_current(city_id, lat, lon, lang),
            self.get_hourly(city_id, lat, lon, lang, hours=24),
            self.get_daily(city_id, lat, lon, lang, days=days),
            self.get_aqi(city_id, lat, lon, lang),
            self.get_alerts(city_id, lat, lon, lang),
        )
        return {
            "current": current,
            "hourly": hourly,
            "daily": daily,
            "aqi": aqi,
            "alerts": alerts,
        }

    @staticmethod
    def _serialize(obj) -> dict:
        """将 dataclass 序列化为 dict"""
        if hasattr(obj, "__dataclass_fields__"):
            return {
                f: getattr(obj, f)
                for f in obj.__dataclass_fields__
            }
        return obj


# 全局单例
weather_service = WeatherService()
