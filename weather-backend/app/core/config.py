"""天气查询平台 - 应用配置管理"""

from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用全局配置"""

    # ── 应用基础 ──
    APP_NAME: str = "WeatherHub"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # ── 数据库 (SQLite) ──
    DATABASE_URL: str = "sqlite+aiosqlite:///./weather.db"

    @property
    def db_url(self) -> str:
        return self.DATABASE_URL

    @property
    def db_url_sync(self) -> str:
        return self.DATABASE_URL.replace("+aiosqlite", "")

    # ── Redis (已禁用) ──
    @property
    def redis_url(self) -> str:
        return ""

    # ── JWT ──
    JWT_SECRET_KEY: str = "weather-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── 外部天气 API ──
    QWEATHER_API_KEY: str = ""
    QWEATHER_BASE_URL: str = "https://devapi.qweather.com/v7"
    OWM_API_KEY: str = ""
    OWM_BASE_URL: str = "https://api.openweathermap.org/data/3.0"
    WAQI_API_TOKEN: str = ""
    WAQI_BASE_URL: str = "https://api.waqi.info"

    # ── 缓存 TTL（秒） ──
    WEATHER_CACHE_TTL_CURRENT: int = 600      # 实时天气 10 分钟
    WEATHER_CACHE_TTL_HOURLY: int = 1800       # 逐小时 30 分钟
    WEATHER_CACHE_TTL_DAILY: int = 7200         # 逐日 2 小时
    WEATHER_CACHE_TTL_AQI: int = 1800           # AQI 30 分钟
    WEATHER_CACHE_TTL_ALERTS: int = 600         # 预警 10 分钟

    # ── 限流 ──
    RATE_LIMIT_ANONYMOUS: int = 60              # 匿名 60次/分钟
    RATE_LIMIT_AUTHENTICATED: int = 120          # 登录 120次/分钟

    # ── CORS ──
    CORS_ORIGINS: list[str] = ["*"]

    # ── 分页 ──
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # 允许旧 .env 中多余字段（DB_*, REDIS_* 等已废弃）


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
