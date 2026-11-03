"""
画像模块（独立库）

与主库的关系：**只读**。本模块不 import 任何写主库的会话方法。
表结构与说明见 models.py，隔离机制见 db.py。
"""

from app.modules.persona.db import (  # noqa: F401
    PersonaBase,
    PersonaSessionLocal,
    get_persona_db,
    persona_engine,
    read_main_exhibitions,
)

__all__ = [
    "PersonaBase",
    "PersonaSessionLocal",
    "get_persona_db",
    "persona_engine",
    "read_main_exhibitions",
]
