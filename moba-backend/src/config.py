"""应用配置"""

import os


class Settings:
    APP_NAME: str = "MOBA Backend"
    APP_VERSION: str = "0.1.0"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./moba.db"
    )
    DATABASE_URL_SYNC: str = "sqlite:///./moba.db"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()
