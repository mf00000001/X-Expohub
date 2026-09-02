"""
数据库引擎 & 会话管理

使用 SQLAlchemy 引擎连接数据库：
- 默认 SQLite（开发零配置）
- 生产可经 settings.DATABASE_URL 切换 MySQL/PG
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

# 数据库连接串（配置驱动；默认 sqlite:///./expohub.db）
DATABASE_URL = settings.DATABASE_URL

engine_kwargs: dict = {"echo": False}
# SQLite 允许多线程访问
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

# 创建引擎
engine = create_engine(DATABASE_URL, **engine_kwargs)

# 启用 SQLite 外键约束
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


def get_db():
    """
    获取数据库会话的依赖注入函数（同步）

    Yields:
        Session: 同步数据库会话，请求结束后自动关闭
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
