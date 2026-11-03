"""
给 exhibitions 表补 category（品类）列。

为什么需要这个脚本：
前端"创建展会"一直在传 category，后端 `Exhibition` 模型从来没有这一列，
Pydantic 默认 `extra=ignore` 把字段静默吞掉——接口返回 200、提示创建成功，
但品类永远是空的。画像的 E1（客群可得性）/ E2（竞争密度）都以品类为前置，
这一列丢了，下游全部算不了。

本仓库没有 Alembic（没有 alembic/ 目录、没有 versions/），所以迁移用
SQLAlchemy 之外的最小幂等脚本：先查 pragma，再决定要不要 ALTER。
重复执行安全。

用法（在 expohub-backend 目录下）：
    python scripts/migrate_add_exhibition_category.py --dry-run
    python scripts/migrate_add_exhibition_category.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_DB = BACKEND / "expohub.db"


def table_has(db: Path, table: str, column: str) -> bool:
    con = sqlite3.connect(db)
    try:
        return any(r[1] == column for r in con.execute("PRAGMA table_info(%s)" % table))
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print("✗ 找不到数据库：%s" % db, file=sys.stderr)
        return 2

    if table_has(db, "exhibitions", "category"):
        print("[OK] exhibitions.category 已存在，无需迁移")
        return 0

    n = sqlite3.connect(db).execute("SELECT COUNT(*) FROM exhibitions").fetchone()[0]
    print("库：%s" % db)
    print("将执行：ALTER TABLE exhibitions ADD COLUMN category VARCHAR(50)")
    print("将执行：CREATE INDEX ix_exhibitions_category ON exhibitions(category)")
    print("影响：%d 行展会（新列全部为 NULL，不会改动任何现有值）" % n)
    if args.dry_run:
        return 0

    con = sqlite3.connect(db)
    try:
        con.execute("ALTER TABLE exhibitions ADD COLUMN category VARCHAR(50)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_exhibitions_category ON exhibitions(category)")
        con.commit()
    finally:
        con.close()

    ok = table_has(db, "exhibitions", "category")
    print("[%s] 迁移完成" % ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
