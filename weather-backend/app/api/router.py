"""天气查询平台 - API 路由注册"""

from fastapi import APIRouter

from app.api.v1.weather import router as weather_router
from app.api.v1.cities import router as cities_router
from app.api.v1.aqi import router as aqi_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.favorites import router as favorites_router
from app.api.v1.auth import router as auth_router
from app.api.v1.indices import router as indices_router
from app.api.v1.history import router as history_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(weather_router)
api_router.include_router(cities_router)
api_router.include_router(aqi_router)
api_router.include_router(alerts_router)
api_router.include_router(favorites_router)
api_router.include_router(indices_router)
api_router.include_router(history_router)
