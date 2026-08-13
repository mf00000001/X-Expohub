"""应用配置 - 支持多环境、JWT、角色权限

环境变量映射（pydantic-settings 自动处理）：
    DATABASE_URL       → database_url
    SECRET_KEY         → secret_key
    CORS_ORIGINS       → cors_origins
    等等...
"""

from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类，从环境变量 /.env 文件读取"""

    # ========== 应用基础 ==========
    app_name: str = "ExpoHub API"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # ========== 数据库（SQLite + aiosqlite 异步驱动） ==========
    # 环境变量 DATABASE_URL 会自动映射到此字段
    # SQLite 示例: sqlite+aiosqlite:///./app.db
    # MySQL  示例: mysql+aiomysql://user:pass@localhost:3306/expo_hub
    database_url: str = "sqlite+aiosqlite:///./app.db"

    # ========== JWT 双令牌认证 ==========
    secret_key: str = "expo-hub-secret-key-change-in-production"
    algorithm: str = "HS256"
    # 访问令牌：短期（15分钟）
    access_token_expire_minutes: int = 15
    # 刷新令牌：长期（7天）
    refresh_token_expire_days: int = 7

    # ========== CORS ==========
    cors_origins: str = "*"

    # ========== 密码策略 ==========
    password_min_length: int = 8
    password_max_length: int = 128

    # ========== 分页 ==========
    page_size_default: int = 20
    page_size_max: int = 100

    @property
    def cors_origin_list(self) -> list[str]:
        """解析 CORS 来源配置"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def refresh_token_expire_minutes(self) -> int:
        """刷新令牌过期时间（分钟）"""
        return self.refresh_token_expire_days * 24 * 60

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        # 允许从环境变量读取所有字段（大小写不敏感）
        # DATABASE_URL → database_url, SECRET_KEY → secret_key
        "case_sensitive": False,
    }


settings = Settings()
