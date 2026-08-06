"""
应用配置管理

使用 Pydantic Settings 从环境变量/.env 文件加载配置，
支持 SQLite（开发）和 MySQL（生产）两种数据库。
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Optional, List

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    """应用环境枚举"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """应用全局配置

    配置项优先级：环境变量 > .env 文件 > 默认值
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- 应用基础配置 ----
    APP_NAME: str = "ExpoHub"
    APP_VERSION: str = "1.0.0"
    APP_ENV: AppEnv = AppEnv.DEVELOPMENT
    DEBUG: bool = True

    # ---- 服务监听 ----
    HOST: str = "0.0.0.0"
    PORT: int = 8002

    # ---- 数据库 ----
    # 默认 SQLite（零配置），生产环境设置 DATABASE_URL 为 MySQL 连接串
    DATABASE_URL: str = "sqlite:///./expohub.db"

    # MySQL 单独配置（可选，作为备选）
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "expohub"
    DB_PASSWORD: str = "expohub123"
    DB_NAME: str = "expohub"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    @property
    def is_sqlite(self) -> bool:
        """判断当前是否使用 SQLite"""
        return self.DATABASE_URL.startswith("sqlite")

    # ---- JWT 令牌配置 ----
    SECRET_KEY: str = "change-me-to-a-secure-random-string-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Access Token 有效期（分钟）
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7     # Refresh Token 有效期（天）

    # ---- CORS 配置 ----
    CORS_ORIGINS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]

    # ---- 分页默认值 ----
    PAGE_DEFAULT: int = 1
    PAGE_SIZE_DEFAULT: int = 20
    PAGE_SIZE_MAX: int = 100

    # ---- 文件上传 ----
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB


# 全局单例配置
settings = Settings()
