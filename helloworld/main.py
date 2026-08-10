"""
HelloWorld 应用入口（FastAPI — 架构师推荐方案）

提供 `/hello` 问候接口和静态文件托管服务。
启动方式: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="HelloWorld", version="1.0.0")


# ========== 数据模型 ==========

class HelloResponse(BaseModel):
    """问候消息响应体"""
    message: str


# ========== API 路由 ==========

@app.get("/api/health", tags=["health"])
async def health_check():
    """
    健康检查接口

    Returns:
        dict: 包含服务状态和版本信息的 JSON 对象
    """
    return {
        "status": "ok",
        "service": "HelloWorld",
        "version": "1.0.0",
    }


@app.get("/hello", response_model=HelloResponse, tags=["hello"])
async def say_hello() -> HelloResponse:
    """
    返回 Hello World 问候消息

    Returns:
        HelloResponse: 包含问候消息的 JSON 对象
    """
    return HelloResponse(message="Hello, World!")


# ========== 托管静态文件（前端页面） ==========
# 注意：StaticFiles 挂载必须在路由注册之后，
# 且设置 html=True 以支持自动查找 index.html

app.mount("/", StaticFiles(directory="static", html=True), name="static")
