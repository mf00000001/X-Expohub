"""天气查询平台 - 城市相关 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.services.city_service import city_service
from app.utils.response import success_response

router = APIRouter(prefix="/cities", tags=["城市"])


@router.get("/search")
async def search_cities(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词"),
    lang: str = Query("zh-CN", description="语言"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """城市模糊搜索"""
    cities = await city_service.search(db, q, lang, limit)
    return success_response({"cities": cities, "total": len(cities)})


@router.get("/geocode")
async def geocode(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    db: AsyncSession = Depends(get_db),
):
    """GPS 坐标反查城市"""
    result = await city_service.geocode(db, lat, lon)
    if not result:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("未找到附近的城市")
    return success_response(result)


@router.get("/hot")
async def get_hot_cities(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """获取热门城市列表"""
    cities = await city_service.get_hot_cities(db, limit)
    return success_response({"cities": cities})


@router.get("/{city_id}")
async def get_city_detail(
    city_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取城市详情"""
    city = await city_service.get_by_id(db, city_id)
    if not city:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("城市不存在")
    return success_response(city)
