"""主路由聚合"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    audit,
    auth,
    booths,
    dashboard,
    exhibitions,
    exhibitors,
    messages,
    procurements,
    teams,
    users,
)

# 主路由
api_router = APIRouter(prefix="/api/v1")

# 注册所有子路由
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(exhibitions.router)
api_router.include_router(exhibitors.router)
api_router.include_router(booths.router)
api_router.include_router(procurements.router)
api_router.include_router(messages.router)
api_router.include_router(teams.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
