"""天气查询平台 - 预警 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.services.city_service import city_service
from app.services.weather_service import weather_service
from app.utils.response import success_response

router = APIRouter(prefix="/alerts", tags=["预警"])


@router.get("/active")
async def get_active_alerts(
    city_id: int | None = Query(None, description="城市ID（可选，不传则返回所有活跃预警）"),
    lang: str = Query("zh"),
    db: AsyncSession = Depends(get_db),
):
    """获取活跃的天气预警"""
    if city_id:
        city_info = await city_service.get_by_id(db, city_id)
        if not city_info:
            from app.core.exceptions import NotFoundException
            raise NotFoundException("城市不存在")
        alerts = await weather_service.get_alerts(
            city_id, city_info["latitude"], city_info["longitude"], lang
        )
        return success_response({"city": city_info, "alerts": alerts})

    # 返回所有热门城市的预警
    hot_cities = await city_service.get_hot_cities(db, limit=20)
    all_alerts = []
    for c in hot_cities:
        alerts = await weather_service.get_alerts(
            c["id"], c["latitude"], c["longitude"], lang
        )
        if alerts:
            for a in alerts:
                a["city"] = c
                all_alerts.append(a)

    return success_response({"total": len(all_alerts), "alerts": all_alerts})
