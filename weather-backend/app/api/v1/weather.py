"""天气查询平台 - 天气相关 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.database.session import get_db
from app.services.city_service import city_service
from app.services.weather_service import weather_service
from app.utils.response import success_response

router = APIRouter(prefix="/weather", tags=["天气"])


def _to_frontend(current, city_info: dict | None = None) -> dict:
    """将后端 CurrentWeather (dataclass 或 dict) 转为前端期望的字段名"""
    # 兼容 dataclass 和 dict
    g = current.get if isinstance(current, dict) else lambda k, d=None: getattr(current, k, d)
    result = {
        "temperature": g("temp"),
        "feels_like": g("feels_like"),
        "humidity": g("humidity"),
        "pressure": g("pressure"),
        "wind_speed": g("wind_speed"),
        "wind_direction": g("wind_deg"),
        "wind_direction_text": g("wind_direction"),
        "visibility": g("visibility") or 10,
        "weather_code": str(g("weather_id") or ""),
        "weather_text": g("weather_main") or g("weather_description") or "",
        "weather_icon": g("weather_icon") or "",
        "uv_index": int(g("uv_index") or 0),
        "observation_time": g("updated_at") or "",
        "is_day": True,
    }
    if city_info:
        result["city_id"] = city_info.get("id")
        result["city_name"] = city_info.get("name", "")
        result["country"] = city_info.get("country", "")
        result["aqi"] = 0
        result["aqi_level"] = ""
    return result


@router.get("/current")
async def get_current_weather(
    city_id: int | None = Query(None, description="城市ID"),
    city: str | None = Query(None, description="城市名称（与 GPS 二选一）"),
    lat: float | None = Query(None, ge=-90, le=90, description="纬度"),
    lon: float | None = Query(None, ge=-180, le=180, description="经度"),
    lang: str = Query("zh", description="语言"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取实时天气

    支持三种查询方式：
    - city_id：按城市 ID
    - city：按城市名称（自动匹配）
    - lat + lon：按 GPS 坐标
    """
    # 解析城市坐标
    city_lat, city_lon, found_city_id = await _resolve_location(
        db, city_id=city_id, city_name=city, lat=lat, lon=lon
    )

    city_info = await city_service.get_by_id(db, found_city_id)
    if not city_info:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("未找到该城市")

    weather = await weather_service.get_current(
        found_city_id, city_lat, city_lon, lang
    )

    return success_response({
        "city": city_info,
        "current": _to_frontend(weather, city_info),
        "source": weather_service.primary.source_name,
    })


@router.get("/hourly")
async def get_hourly_forecast(
    city_id: int = Query(..., description="城市ID"),
    hours: int = Query(24, ge=1, le=48, description="小时数"),
    lang: str = Query("zh"),
    db: AsyncSession = Depends(get_db),
):
    """获取逐小时预报（最多 48 小时）"""
    city_info = await city_service.get_by_id(db, city_id)
    if not city_info:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("未找到该城市")

    hourly = await weather_service.get_hourly(
        city_id, city_info["latitude"], city_info["longitude"], lang, hours
    )
    return success_response({
        "city": city_info,
        "hourly": hourly,
    })


@router.get("/daily")
async def get_daily_forecast(
    city_id: int = Query(..., description="城市ID"),
    days: int = Query(7, ge=1, le=15, description="天数"),
    lang: str = Query("zh"),
    db: AsyncSession = Depends(get_db),
):
    """获取逐日预报（7-15 天）"""
    city_info = await city_service.get_by_id(db, city_id)
    if not city_info:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("未找到该城市")

    daily = await weather_service.get_daily(
        city_id, city_info["latitude"], city_info["longitude"], lang, days
    )
    return success_response({
        "city": city_info,
        "daily": daily,
    })


@router.get("/full")
async def get_full_weather(
    city_id: int | None = Query(None),
    city: str | None = Query(None),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    days: int = Query(7, ge=1, le=15),
    lang: str = Query("zh"),
    db: AsyncSession = Depends(get_db),
):
    """
    一次性获取完整天气数据（实时 + 逐小时 + 逐日 + AQI + 预警）
    推荐首页使用，减少请求次数
    """
    city_lat, city_lon, found_city_id = await _resolve_location(
        db, city_id=city_id, city_name=city, lat=lat, lon=lon
    )

    city_info = await city_service.get_by_id(db, found_city_id)
    if not city_info:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("未找到该城市")

    data = await weather_service.get_full_weather(
        found_city_id, city_lat, city_lon, lang, days
    )
    # 翻译逐小时预报
    hourly_data = []
    for h in (data.get("hourly") or []):
        g = h.get if isinstance(h, dict) else lambda k, d=None: getattr(h, k, d)
        hourly_data.append({
            "time": g("time"), "temperature": g("temp"),
            "weather_code": str(g("weather_id", "")), "weather_text": g("weather_main") or g("weather_description") or "",
            "weather_icon": g("weather_icon") or "", "wind_speed": g("wind_speed"),
            "humidity": g("humidity"), "pop": int(g("rain_probability") or 0), "is_day": True,
        })
    # 翻译逐日预报
    daily_data = []
    for d in (data.get("daily") or []):
        g = d.get if isinstance(d, dict) else lambda k, de=None: getattr(d, k, de)
        daily_data.append({
            "date": g("date"), "temp_max": g("temp_max"), "temp_min": g("temp_min"),
            "weather_code": str(g("weather_id", "")), "weather_text": g("weather_main") or g("weather_description") or "",
            "weather_icon": g("weather_icon") or "", "sunrise": "", "sunset": "",
            "humidity": g("humidity") or 50, "wind_speed": g("wind_speed") or 0,
            "pop": int(g("rain_probability") or 0), "uv_index": 0,
        })

    return success_response({
        "city": city_info,
        "current": _to_frontend(data["current"], city_info),
        "hourly": hourly_data,
        "daily": daily_data,
        "aqi": data.get("aqi"),
        "alerts": data.get("alerts", []),
    })


async def _resolve_location(
    db: AsyncSession,
    city_id: int | None = None,
    city_name: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[float, float, int]:
    """解析位置参数，返回 (lat, lon, city_id)"""
    if city_id:
        city_info = await city_service.get_by_id(db, city_id)
        if city_info:
            return city_info["latitude"], city_info["longitude"], city_id
        raise NotFoundException("城市不存在")

    if lat is not None and lon is not None:
        geocode = await city_service.geocode(db, lat, lon)
        if geocode:
            return lat, lon, geocode["id"]
        # 没有匹配城市，直接用 GPS
        return lat, lon, 0

    if city_name:
        cities = await city_service.search(db, city_name, limit=1)
        if cities:
            c = cities[0]
            return c["latitude"], c["longitude"], c["id"]
        raise NotFoundException(f"未找到城市: {city_name}")

    from app.core.exceptions import ValidationException
    raise ValidationException("请提供 city_id、city 或 lat+lon 参数")
