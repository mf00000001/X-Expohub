"""天气查询平台 - 城市服务"""

from __future__ import annotations

import json

from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.redis import get_redis
from app.models import City


class CityService:
    """城市查询服务"""

    async def search(
        self,
        db: AsyncSession,
        query: str,
        lang: str = "zh-CN",
        limit: int = 10,
    ) -> list[dict]:
        """城市模糊搜索"""
        # 优先查缓存
        cache_key = f"cities:search:{query}:{lang}"
        try:
            redis = await get_redis()
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        # 数据库搜索
        stmt = (
            select(City)
            .where(
                City.name.ilike(f"%{query}%")
                | City.name_en.ilike(f"%{query}%")
            )
            .order_by(City.population.desc().nullslast(), City.priority.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        cities = result.scalars().all()

        city_list = [
            {
                "id": c.id,
                "name": c.name,
                "name_en": c.name_en,
                "country": c.country,
                "country_code": c.country_code,
                "admin1": c.admin1,
                "latitude": c.latitude,
                "longitude": c.longitude,
            }
            for c in cities
        ]

        # 写入缓存
        try:
            redis = await get_redis()
            await redis.setex(cache_key, 3600, json.dumps(city_list, ensure_ascii=False))
        except Exception:
            pass

        return city_list

    async def geocode(
        self,
        db: AsyncSession,
        lat: float,
        lon: float,
    ) -> dict | None:
        """GPS 反查最近城市（PostGIS 空间查询）"""
        stmt = text("""
            SELECT id, name, name_en, country, country_code, admin1,
                   latitude, longitude,
                   ST_Distance(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) AS dist
            FROM cities
            WHERE geom IS NOT NULL
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
        """)
        result = await db.execute(stmt, {"lat": lat, "lon": lon})
        row = result.first()
        if not row:
            return None

        # 距离 > 50km 认为不在任何已知城市附近
        if row.dist and row.dist > 0.5:  # 约 50km
            return None

        return {
            "id": row.id,
            "name": row.name,
            "name_en": row.name_en,
            "country": row.country,
            "country_code": row.country_code,
            "admin1": row.admin1,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "distance_km": round(row.dist * 111, 1) if row.dist else None,
        }

    async def get_hot_cities(self, db: AsyncSession, limit: int = 20) -> list[dict]:
        """获取热门城市"""
        stmt = (
            select(City)
            .where(City.is_hot == True)
            .order_by(City.priority.desc(), City.population.desc().nullslast())
            .limit(limit)
        )
        result = await db.execute(stmt)
        cities = result.scalars().all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "country": c.country,
                "country_code": c.country_code,
                "latitude": c.latitude,
                "longitude": c.longitude,
            }
            for c in cities
        ]

    async def get_by_id(self, db: AsyncSession, city_id: int) -> dict | None:
        """根据 ID 获取城市"""
        stmt = select(City).where(City.id == city_id)
        result = await db.execute(stmt)
        city = result.scalar_one_or_none()
        if not city:
            return None
        return {
            "id": city.id,
            "name": city.name,
            "name_en": city.name_en,
            "country": city.country,
            "country_code": city.country_code,
            "admin1": city.admin1,
            "latitude": city.latitude,
            "longitude": city.longitude,
            "timezone": city.timezone,
        }


city_service = CityService()
