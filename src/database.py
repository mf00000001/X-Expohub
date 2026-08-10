"""数据库连接与会话管理（SQLite + aiosqlite 异步驱动）"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from src.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

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
    获取数据库会话的依赖注入函数（异步）

    Yields:
        AsyncSession: 异步数据库会话，请求结束后自动关闭
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()
