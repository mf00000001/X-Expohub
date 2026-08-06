"""
数据库引擎 & 会话管理（SQLite）

使用 SQLAlchemy 同步引擎连接 SQLite 数据库。
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# SQLite 数据库文件路径（相对于项目根目录）
DATABASE_URL = "sqlite:///./expohub.db"

# 创建同步引擎
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # SQLite 允许多线程
)

# 启用 SQLite 外键约束
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
