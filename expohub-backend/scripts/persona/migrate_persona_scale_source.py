"""
画像库轻量迁移：给 expo 加 scale_source 列。

为什么不走 alembic：画像库是按设计"可随时重建"的派生库（`init_db.py --force` 一秒钟重建），
上迁移框架反而给它加了个不必要的历史包袱。但**重建会丢掉人工补录的数据**，
所以实际运行时还是需要一条就地加列的路径。

幂等：列已存在就跳过，可反复执行。

用法：
    python scripts/persona/migrate_persona_scale_source.py --dry-run
    python scripts/persona/migrate_persona_scale_source.py
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "persona.db"


def cols(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print("✗ 库不存在：%s" % db, file=sys.stderr)
        return 2

    con = sqlite3.connect(db)
    have = cols(con, "expo")
    todo = []
    if "scale_source" not in have:
        todo.append("ALTER TABLE expo ADD COLUMN scale_source VARCHAR(20)")
        todo.append("CREATE INDEX IF NOT EXISTS ix_expo_scale_source ON expo (scale_source)")

    if not todo:
        print("已是最新，无需迁移。")
        return 0

    print("将执行 %d 条：" % len(todo))
    for s in todo:
        print("  " + s)
    if args.dry_run:
        print("--dry-run，未执行。")
        return 0

    for s in todo:
        con.execute(s)
    con.commit()

    # 回读核验：ALTER TABLE 静默失败在 SQLite 上不会报错，只能靠复查表结构兜住
    after = cols(con, "expo")
    assert "scale_source" in after, "迁移后仍无 scale_source 列"
    n = con.execute("SELECT COUNT(*) FROM expo").fetchone()[0]
    print("✓ 迁移完成；expo 共 %d 行，列数 %d → %d" % (n, len(have), len(after)))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
