"""FastAPI Hello World 应用"""

from fastapi import FastAPI

app = FastAPI(title="Hello World API", version="1.0.0")


@app.get("/")
async def root() -> dict[str, str]:
    """
    根路径接口，返回 Hello World 消息

    Returns:
        包含问候消息的字典
    """
    return {"message": "Hello World"}
