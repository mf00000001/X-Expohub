"""天气查询平台 - 统一响应格式"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def success_response(data: Any = None, message: str = "ok") -> JSONResponse:
    """成功响应"""
    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "data": data,
            "message": message,
        },
    )


def error_response(
    code: int,
    message: str,
    detail: str | None = None,
) -> JSONResponse:
    """错误响应"""
    return JSONResponse(
        status_code=code,
        content={
            "code": code,
            "data": None,
            "message": message,
            "detail": detail,
        },
    )
