"""
前端控制台回传收集（演示监控用）

前端 main.ts 注入全局钩子：console.error / unhandledrejection / window error
会带 X-Debug-Log 头 POST 到此端点，落盘 JSONL（默认 ./data/console_log.jsonl）。

- 端点无条件注册，但要求请求头 X-Debug-Log == DEBUG_TOKEN（防生产滥用）
- 纯观测：写入失败不影响任何业务
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Header, Request
from starlette.responses import JSONResponse

DEBUG_TOKEN = "expohub-demo-monitor"
LOG_PATH = os.environ.get("CONSOLE_LOG_PATH", "./data/console_log.jsonl")


router = APIRouter(prefix="/debug", tags=["调试"])


@router.post("/console")
async def capture_console(request: Request, x_debug_log: str = Header(default="")):
    """前端控制台错误回传（仅限带调试头的请求）"""
    if x_debug_log != DEBUG_TOKEN:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    try:
        body = await request.json()
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": body.get("level", "log"),
            "msg": str(body.get("msg", ""))[:2000],
            "url": str(body.get("url", ""))[:300],
        }
        os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return JSONResponse(content={"ok": True})
    except Exception:
        return JSONResponse(content={"ok": True})  # 静默，避免干扰演示
