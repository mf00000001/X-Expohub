"""
ExpoHub API 应用入口

FastAPI 应用初始化，包含：
- CORS 中间件
- 路由注册
- 全局异常处理
- 启动时自动创建 SQLite 数据库表（异步 lifespan）

启动方式：
    python3 -m uvicorn app.main:app --port 8002
    python3 -m uvicorn app.main:app --port 8002 --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    - startup: 自动创建 SQLite 数据库表
    - shutdown: （暂无清理需求）
    """
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    print(f"📦 数据库: SQLite + aiosqlite ({db_path})")
    print(f"🔧 正在创建/检查数据库表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ 数据库表已就绪")
    yield


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用

    Returns:
        配置好的 FastAPI 应用实例
    """
    app = FastAPI(
        title=settings.app_name,
        description="ExpoHub 展会管理平台 API - 支持游客、展商、主办方、老板四类角色",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        contact={
            "name": "ExpoHub Team",
            "url": "https://expo-hub.dev",
        },
        license_info={
            "name": "MIT",
        },
    )

    # ========== CORS 中间件 ==========
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ========== 全局异常处理 ==========
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全局异常捕获，返回统一错误格式"""
        return JSONResponse(
            status_code=500,
            content={
                "detail": "服务器内部错误",
                "error_code": "INTERNAL_ERROR",
            },
        )

    # ========== 注册路由 ==========
    app.include_router(router)

    return app


app = create_app()


@app.get("/", tags=["health"])
async def root():
    """根路径健康检查"""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": "2.0.0",
        "environment": settings.environment,
        "database": "SQLite + aiosqlite",
    }
