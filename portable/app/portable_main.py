"""ExpoHub 便携版入口。

在**未改动**的 `app.main:app` 之上叠加两层能力：

1. 同源托管前端静态产物（Vite dist + SPA fallback）—— 前后端同端口，
   零 CORS、零代理、只起一个进程。
2. 真实健康检查 ``/api/health`` —— 验证数据库可连通，而不只是"进程还活着"。

本文件放在便携包内、**不落进 ``app/`` 包**，因此从 git 拉取最新代码时
不会与它冲突（见包内 ``检查更新.bat``）。

环境变量（均有兜底默认值，启动脚本会显式注入绝对路径）：

===============  ==========================================================
FRONTEND_DIR     前端产物目录，默认 ``<本文件同级>/web``
HOST / PORT      监听地址，默认 ``127.0.0.1:8002``
===============  ==========================================================
"""
from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.abspath(
    os.environ.get("FRONTEND_DIR") or os.path.join(BASE_DIR, "web")
)
INDEX = os.path.join(WEB_DIR, "index.html")

# ---- 启动前置校验：缺前端产物就明确报错，而不是起一个只返回 JSON 的假服务 ----
if not os.path.isfile(INDEX):
    sys.stderr.write(
        f"[致命] 前端产物缺失，未找到 {INDEX}\n"
        f"       请确认 web/ 目录随包一起解压完整，或设置 FRONTEND_DIR 指向正确位置。\n"
    )
    raise SystemExit(2)

# app 包与本文件同级，确保可导入（不依赖 CWD）
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI                                   # noqa: E402
from fastapi.responses import FileResponse, JSONResponse      # noqa: E402
from fastapi.staticfiles import StaticFiles                   # noqa: E402
from starlette.exceptions import HTTPException as HTTPError   # noqa: E402

from app.main import app                                      # noqa: E402

# 归后端所有的路径前缀，不做 SPA 回落
_RESERVED = {"api", "docs", "redoc", "openapi.json"}


def _yield_root_route(application: FastAPI) -> None:
    """让出根路径。

    ``app.main`` 里 ``@app.get("/")`` 返回健康检查 JSON，且先于本文件注册、
    会抢先匹配。这里把它摘掉，根路径改由前端页面接管；
    健康检查迁移到 ``/api/health``。
    """
    application.router.routes = [
        route
        for route in application.router.routes
        if not (
            getattr(route, "path", None) == "/"
            and "GET" in (getattr(route, "methods", None) or set())
        )
    ]


_yield_root_route(app)


@app.get("/api/health", include_in_schema=False)
async def _health():
    """健康检查：真连一次数据库，避免"端口开了但应用还不能用"。"""
    from sqlalchemy import text

    from app.models.base import engine

    payload = {"ok": True, "app": "ExpoHub", "mode": "portable"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        payload["database"] = "ok"
        status = 200
    except Exception as exc:  # noqa: BLE001 —— 健康检查须吞掉一切异常并如实上报
        payload["ok"] = False
        payload["database"] = f"{type(exc).__name__}: {exc}"
        status = 503
    return JSONResponse(status_code=status, content=payload)


# Vite 产物：/assets/* 直接由 StaticFiles 托管（支持 Range / ETag）
_assets_dir = os.path.join(WEB_DIR, "assets")
if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="portable-assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def _spa_fallback(full_path: str):
    """非 /api 路径：存在的静态文件原样返回，否则回落 index.html（前端路由）。"""
    if full_path.split("/", 1)[0] in _RESERVED:
        raise HTTPError(status_code=404)

    if full_path:
        candidate = os.path.join(WEB_DIR, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        # 带扩展名却找不到 = 真静态资源缺失。如实 404，
        # 否则浏览器会拿到一份 HTML 当 JS/SVG 解析，报出误导性的语法错误。
        if "." in os.path.basename(full_path):
            raise HTTPError(status_code=404)

    return FileResponse(INDEX, headers={"Cache-Control": "no-cache"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8002")),
        log_level="info",
        access_log=False,
    )
