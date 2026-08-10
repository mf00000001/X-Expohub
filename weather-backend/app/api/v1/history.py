"""天气查询平台 - 历史天气 API"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.services.city_service import city_service
from app.services.weather_service import weather_service
from app.utils.response import success_response

router = APIRouter(prefix="/history", tags=["历史天气"])


@router.get("")
async def get_history_weather(
    city_id: int = Query(..., description="城市 ID"),
    start_date: str | None = Query(
        None,
        description="开始日期 (yyyy-MM-dd)，默认 7 天前",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    end_date: str | None = Query(
        None,
        description="结束日期 (yyyy-MM-dd)，默认昨天",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    lang: str = Query("zh", description="语言"),
    db: AsyncSession = Depends(get_db),
):
    """
    查询历史天气数据

    - 默认查询最近 7 天（不含今天）
    - 支持自定义日期范围
    - 最多查询 30 天历史数据

    返回每日的温度、天气状况、湿度、风速等信息。
    """
    city_info = await city_service.get_by_id(db, city_id)
    if not city_info:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("城市不存在")

    # 解析日期范围
    today = date.today()

    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        end = today - timedelta(days=1)  # 昨天

    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        start = end - timedelta(days=6)  # 默认 7 天

    # 校验日期范围
    if start > end:
        from app.core.exceptions import ValidationException
        raise ValidationException("开始日期不能晚于结束日期")

    if end >= today:
        from app.core.exceptions import ValidationException
        raise ValidationException("结束日期不能是今天或未来日期")

    max_days = 30
    if (end - start).days > max_days:
        from app.core.exceptions import ValidationException
        raise ValidationException(f"最多查询 {max_days} 天历史数据")

    # 获取历史天气
    history = await weather_service.get_history(
        city_id,
        city_info["latitude"],
        city_info["longitude"],
        start.isoformat(),
        end.isoformat(),
        lang,
    )

    return success_response({
        "city": city_info,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "total_days": len(history),
        "history": history,
    })


@router.get("/yesterday")
async def get_yesterday_weather(
    city_id: int = Query(..., description="城市 ID"),
    lang: str = Query("zh", description="语言"),
    db: AsyncSession = Depends(get_db),
):
    """获取昨天天气（快捷接口）"""
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    city_info = await city_service.get_by_id(db, city_id)
    if not city_info:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("城市不存在")

    history = await weather_service.get_history(
        city_id,
        city_info["latitude"],
        city_info["longitude"],
        yesterday,
        yesterday,
        lang,
    )

    return success_response({
        "city": city_info,
        "date": yesterday,
        "weather": history[0] if history else None,
    })
