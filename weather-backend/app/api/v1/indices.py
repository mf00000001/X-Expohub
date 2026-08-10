"""天气查询平台 - 生活指数 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import LIFE_INDEX_TYPES
from app.database.session import get_db
from app.services.city_service import city_service
from app.services.weather_service import weather_service
from app.utils.response import success_response

router = APIRouter(prefix="/indices", tags=["生活指数"])


@router.get("")
async def get_life_indices(
    city_id: int = Query(..., description="城市 ID"),
    index_type: str | None = Query(
        None,
        description=f"指数类型: {', '.join(f'{k}={v}' for k, v in LIFE_INDEX_TYPES.items())}",
    ),
    lang: str = Query("zh", description="语言"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取生活指数

    支持的生活指数类型：
    - 1: 运动指数
    - 2: 洗车指数
    - 3: 穿衣指数
    - 4: 钓鱼指数
    - 5: 紫外线指数
    - 6: 旅游指数
    - 7: 过敏指数
    - 8: 舒适度指数
    - 9: 感冒指数
    - 10: 空气污染扩散条件指数
    - 11: 空调开启指数
    - 12: 太阳镜指数
    - 13: 化妆指数
    - 14: 晾晒指数
    - 15: 交通指数
    - 16: 防晒指数

    不传 index_type 则返回所有可用指数。
    """
    city_info = await city_service.get_by_id(db, city_id)
    if not city_info:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("城市不存在")

    # 从天气服务获取生活指数数据
    indices = await weather_service.get_life_indices(
        city_id,
        city_info["latitude"],
        city_info["longitude"],
        lang,
    )

    # 过滤指定类型
    if index_type and index_type in indices:
        indices = {index_type: indices[index_type]}

    # 为每个指数补充中文名称
    enriched = {}
    for key, value in indices.items():
        enriched[key] = {
            "type": key,
            "name": LIFE_INDEX_TYPES.get(key, f"指数 {key}"),
            **value,
        }

    return success_response({
        "city": city_info,
        "indices": enriched,
        "index_types": LIFE_INDEX_TYPES,
    })
