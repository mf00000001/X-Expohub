"""
画像库 schema 迁移：新增估算相关列与表

为什么要单独一个迁移脚本而不是顺手 `create_all`：
SQLAlchemy 的 `create_all` **只会建缺失的表，不会给已存在的表加列**。
`expo` 表已经有数据，新加的 4 个列（name_official / name_raw /
data_quality / quality_note）必须靠 ALTER TABLE 补上，否则 ORM 查询
会直接报 "no such column"。

SQLite 的 ADD COLUMN 不支持 IF NOT EXISTS，所以先读 PRAGMA 判断，
整个脚本幂等，可以反复跑。

用法：
    python scripts/persona/migrate_estimate.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from app.modules.persona.db import PersonaSessionLocal, persona_engine  # noqa: E402
from app.modules.persona.models import ALL_TABLES, ExpoEstimate, PersonaBase  # noqa: E402

# 列定义必须与 models.py 保持一致。这里不能用 Mapped 的元数据自动生成，
# 因为 SQLite 的 ALTER 只要类型和默认值，ORM 层的约束（index/comment）它不认。
NEW_COLUMNS: list[tuple[str, str]] = [
    ("name_official", "VARCHAR(200)"),
    ("name_raw", "VARCHAR(300)"),
    ("data_quality", "VARCHAR(20)"),
    ("quality_note", "VARCHAR(300)"),
]


def existing_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印将执行的语句")
    args = ap.parse_args()

    print(f"数据库: {persona_engine.url}")
    with persona_engine.begin() as conn:
        cols = existing_columns(conn, "expo")
        todo = [(n, t) for n, t in NEW_COLUMNS if n not in cols]

        if not todo:
            print("expo 表列已齐全，无需迁移")
        for name, ddl_type in todo:
            sql = f"ALTER TABLE expo ADD COLUMN {name} {ddl_type}"
            if args.dry_run:
                print("[dry] " + sql)
            else:
                conn.execute(text(sql))
                print("已加列: " + name)

    if args.dry_run:
        print("[dry] 跳过建表 (create_all)")
        return 0

    # 新表（expo_estimate）可以用 create_all，它不会碰已有表
    PersonaBase.metadata.create_all(
        bind=persona_engine,
        tables=[ExpoEstimate.__table__],
    )
    print("已确保表存在: expo_estimate")

    # 复核：ORM 层能查才算真的成功
    with PersonaSessionLocal() as db:
        n = db.execute(text("select count(*) from expo_estimate")).scalar_one()
        expo_n = db.execute(text("select count(*) from expo where name_official is not null")).scalar_one()
        print(f"复核: expo_estimate {n} 行, expo.name_official 已填 {expo_n} 行")

    print(f"表清单: {[t.__tablename__ for t in ALL_TABLES]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
