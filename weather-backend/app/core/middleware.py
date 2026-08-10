"""天气查询平台 - 中间件"""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class TimingMiddleware(BaseHTTPMiddleware):
    """请求耗时中间件"""

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start
        response.headers["X-Response-Time"] = f"{elapsed:.4f}s"
        return response


def setup_middlewares(app: FastAPI) -> None:
    """注册所有中间件"""

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 响应时间
    app.add_middleware(TimingMiddleware)
