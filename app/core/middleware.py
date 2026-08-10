"""中间件：请求日志、CORS、限流"""

from __future__ import annotations

import time
import logging
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger("expo_hub")


def setup_middlewares(app: FastAPI) -> None:
    """
    配置所有中间件

    Args:
        app: FastAPI 应用实例
    """

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_CREDENTIALS,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )

    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable):
        """记录所有 HTTP 请求"""
        start_time = time.time()

        # 请求信息
        method = request.method
        url = str(request.url.path)
        client_ip = request.client.host if request.client else "unknown"

        response = await call_next(request)

        # 计算耗时
        duration = time.time() - start_time

        # 日志记录
        logger.info(
            f"{client_ip} - {method} {url} - {response.status_code} - {duration:.3f}s"
        )

        # 添加响应头
        response.headers["X-Process-Time"] = f"{duration:.3f}"

        return response
