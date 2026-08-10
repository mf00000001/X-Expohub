"""天气查询平台 - AQI 空气质量 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.services.city_service import city_service
from app.services.weather_service import weather_service
from app.utils.response import success_response

router = APIRouter(prefix="/aqi", tags=["空气质量"])


@router.get("/current")
async def get_current_aqi(
    city_id: int = Query(..., description="城市ID"),
    lang: str = Query("zh"),
    db: AsyncSession = Depends(get_db),
):
    """获取当前空气质量指数"""
    city_info = await city_service.get_by_id(db, city_id)
    if not city_info:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("城市不存在")

    aqi = await weather_service.get_aqi(
        city_id, city_info["latitude"], city_info["longitude"], lang
    )
    if not aqi:
        return success_response(None, message="该城市暂无空气质量数据")

    return success_response({
        "city": city_info,
        "aqi": aqi,
    })
