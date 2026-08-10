"""数据库会话管理 — 异步 SQLAlchemy + aiosqlite"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 异步数据库引擎 (SQLite + aiosqlite)
engine = create_async_engine(
    settings.db_url,
    echo=settings.DEBUG,
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


async def get_db():
    """
    获取异步数据库会话（FastAPI 依赖注入用）

    Yields:
        异步数据库会话
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
