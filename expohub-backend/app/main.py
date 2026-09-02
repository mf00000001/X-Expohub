"""
ExpoHub API 应用入口

FastAPI 应用初始化，包含：
- CORS 中间件
- 全局异常处理
- 路由注册
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.models.base import Base, engine
# V2.0: 确保新模型被 SQLAlchemy 发现
import app.models.membership  # noqa: F401
import app.models.micro_booth  # noqa: F401
# V2.2
import app.models.analytics  # noqa: F401
import app.models.points  # noqa: F401
import app.models.checkin  # noqa: F401
import app.models.notification  # noqa: F401
# V3.0: 预约/收藏落库（安全评审 P0-3）
import app.models.appointment  # noqa: F401
import app.models.favorite  # noqa: F401
# V3.1: 展馆
import app.models.venue  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：创建所有数据库表
    Base.metadata.create_all(bind=engine)
    yield
    # 关闭时：清理资源
    pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# ---- CORS 中间件 ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# ---- 全局异常处理器 ----
register_exception_handlers(app)

# ---- 注册路由 ----
from app.modules.identity.auth import router as auth_router
from app.modules.expo.exhibitions import router as exhibitions_router
from app.modules.expo.booths import router as booths_router
from app.modules.exhibitor.products import router as products_router
from app.modules.matching.procurements import router as procurements_router
from app.modules.interaction.messages import router as messages_router
from app.modules.interaction.reviews import router as reviews_router
from app.modules.analytics.dashboard import router as dashboard_router
from app.modules.exhibitor.exhibitors import router as exhibitors_router
from app.modules.expo.registrations import router as registrations_router
from app.modules.expo.categories import router as categories_router
from app.modules.expo.micro_booths import router as micro_booths_router
from app.modules.analytics.analytics import router as analytics_router
from app.modules.exhibitor.exhibitor_analytics import router as exhibitor_analytics_router
from app.modules.identity.points import router as points_router
from app.modules.interaction.notifications import router as notifications_router
from app.modules.analytics.growth import router as growth_router
from app.modules.interaction.favorites import router as favorites_router
from app.modules.matching.appointments import router as appointments_router
from app.modules.matching.recommendations import router as recommendations_router
from app.modules.interaction.poster import router as poster_router

app.include_router(auth_router, prefix="/api")
app.include_router(exhibitions_router, prefix="/api")
app.include_router(booths_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(procurements_router, prefix="/api")
app.include_router(messages_router, prefix="/api")
app.include_router(reviews_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(exhibitors_router, prefix="/api")
app.include_router(registrations_router, prefix="/api")
app.include_router(categories_router, prefix="/api")
app.include_router(micro_booths_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(exhibitor_analytics_router, prefix="/api")
app.include_router(points_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(growth_router, prefix="/api")
app.include_router(favorites_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
from app.modules.expo.venues import router as venues_router
app.include_router(venues_router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(poster_router, prefix="/api")


@app.get("/")
def root():
    """健康检查"""
    return {
        "success": True,
        "code": "OK",
        "message": f"{settings.APP_NAME} v{settings.APP_VERSION} 运行中",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
