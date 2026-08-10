"""天气查询平台 - SQLAlchemy 声明基类（从 session 模块重导出）"""

from app.database.session import Base

__all__ = ["Base"]
