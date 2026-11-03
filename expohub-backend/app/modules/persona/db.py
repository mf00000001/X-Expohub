"""
画像库独立会话（与主库隔离）

设计约束（2026-11-03 决策：先不动原数据库，画像单独建库）：

1. **独立 DeclarativeBase** —— PersonaBase 不是 app.models.base.Base。
   主库启动时 `Base.metadata.create_all()` 看不到画像表，画像库 `create_all()`
   也碰不到主库表。两边永远不可能互相建表。
2. **独立 SQLite 文件** —— 默认 `sqlite:///./persona.db`，由 settings.PERSONA_DATABASE_URL 控制。
3. **不建外键到主库** —— 跨库 FK 在 SQLite 里不成立，只用 `source_exhibition_id`
   做逻辑关联；一致性靠 scripts/persona/check_orphans.py 兜底。
4. **不走 alembic** —— 画像数据可重建（爬取/录入，不是用户资产），
   直接 create_all 即可，省掉迁移历史。
5. **主库只读** —— 需要展会基础信息时用 read_main_exhibitions()，只 SELECT。
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class PersonaBase(DeclarativeBase):
    """画像库声明式基类（独立于主库 Base）"""
    pass


PERSONA_DATABASE_URL = settings.PERSONA_DATABASE_URL

_engine_kwargs: dict = {"echo": False}
if PERSONA_DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

persona_engine = create_engine(PERSONA_DATABASE_URL, **_engine_kwargs)


def enable_sqlite_fk(engine) -> None:
    """
    开启 SQLite 外键约束。

    **不开这个 PRAGMA，ondelete='CASCADE' 完全不生效** —— 删展会时观测和名录
    会变成孤儿静默留存。冒烟测试里踩过一次，所以抽成公共函数复用。
    """

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


if PERSONA_DATABASE_URL.startswith("sqlite"):
    enable_sqlite_fk(persona_engine)


PersonaSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=persona_engine
)


def get_persona_db():
    """画像库会话依赖注入（FastAPI 用）"""
    db = PersonaSessionLocal()
    try:
        yield db
    finally:
        db.close()


def read_main_exhibitions(ids: list[int] | None = None) -> list[dict]:
    """
    只读主库展会表。**严禁在此函数里写主库。**

    画像库里很多展还没进主库（爬来但未上架），所以这个函数返回空列表是正常情况，
    调用方必须容忍。
    """
    from app.models.base import SessionLocal  # 延迟导入：避免主库引擎在导入期被初始化
    from app.models.exhibition import Exhibition

    db = SessionLocal()
    try:
        q = db.query(
            Exhibition.id,
            Exhibition.title,
            Exhibition.start_date,
            Exhibition.end_date,
            Exhibition.location,
            Exhibition.visitor_count,
            Exhibition.status,
        )
        if ids:
            q = q.filter(Exhibition.id.in_(ids))
        return [dict(row._mapping) for row in q.all()]
    finally:
        db.close()
