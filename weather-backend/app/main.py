"""天气查询平台 - FastAPI 应用入口"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.middleware import setup_middlewares

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("weather_hub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🌤️ {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    yield
    logger.info("🛑 应用关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="🌤️ 天气查询平台 API - 支持实时天气、预报、AQI、预警",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# 中间件
setup_middlewares(app)

# 路由
app.include_router(api_router)


# 全局异常处理
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "data": None,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未捕获异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "data": None,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else None,
        },
    )


# 健康检查
@app.get("/health", tags=["系统"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/", tags=["系统"])
async def root():
    return {
        "message": f"欢迎使用 {settings.APP_NAME} API 🌤️",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else None,
    }
