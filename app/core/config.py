"""应用配置管理（SQLite + aiosqlite）"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用全局配置"""

    # 应用基础配置
    APP_NAME: str = "ExpoHub"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # 数据库配置 — 默认 SQLite + aiosqlite
    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"

    @property
    def db_url(self) -> str:
        """获取数据库连接 URL"""
        return self.DATABASE_URL

    # JWT 配置
    JWT_SECRET_KEY: str = "super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 令牌黑名单
    TOKEN_BLACKLIST_ENABLED: bool = False  # SQLite 模式默认关闭

    # 密码哈希
    BCRYPT_ROUNDS: int = 12

    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: list[str] = ["*"]
    CORS_HEADERS: list[str] = ["*"]

    # 分页
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 全局单例
settings = Settings()
