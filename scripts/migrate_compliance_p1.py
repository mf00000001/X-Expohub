"""合规第一批字段迁移（2026-10-19）

给 users 表补两列（模型已声明，SQLite 库需要 ALTER）：

    personalized_recommend  BOOLEAN NOT NULL DEFAULT 1   -- 是否开启个性化推荐
    privacy_agreed_at       DATETIME NULL                -- 同意《用户协议》《隐私政策》的时间

设计：幂等、可重复执行、默认自动备份；不动任何业务数据。

用法：
    python scripts/migrate_compliance_p1.py --dry-run
    python scripts/migrate_compliance_p1.py
    python scripts/migrate_compliance_p1.py --db path/to/expohub.db
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DEFAULT_DB = os.path.join("expohub-backend", "expohub.db")

COLUMNS = [
    ("personalized_recommend", "BOOLEAN NOT NULL DEFAULT 1"),
    ("privacy_agreed_at", "DATETIME"),
]


def run(db_path: str, dry_run: bool) -> int:
    if not os.path.exists(db_path):
        print(f"[XX] 数据库不存在：{db_path}")
        return 1

    conn = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    cur = conn.cursor()
    existing = [row[1] for row in cur.execute('PRAGMA table_info("users")')]

    todo = [(name, ddl) for name, ddl in COLUMNS if name not in existing]
    if not todo:
        print("[--] 字段已齐全，无需迁移")
        conn.close()
        return 0

    for name, ddl in todo:
        print(f"[..] users: 新增列 {name} {ddl}")
        if not dry_run:
            cur.execute(f'ALTER TABLE users ADD COLUMN "{name}" {ddl}')
    if dry_run:
        print(f"\n=== DRY-RUN：本会新增 {len(todo)} 列（未写库）===")
        conn.close()
        return 0

    conn.commit()
    # 回填：老账号默认开启个性化推荐
    cur.execute("UPDATE users SET personalized_recommend=1 WHERE personalized_recommend IS NULL")
    conn.commit()
    cols = [row[1] for row in cur.execute('PRAGMA table_info("users")')]
    print("\n=== 迁移完成 ===")
    print("  users 现有列数：", len(cols))
    print("  personalized_recommend 存在：", "personalized_recommend" in cols)
    print("  privacy_agreed_at 存在：", "privacy_agreed_at" in cols)
    print("  已开启个性化推荐的用户数：",
          cur.execute("SELECT COUNT(*) FROM users WHERE personalized_recommend=1").fetchone()[0])
    conn.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="合规第一批字段迁移")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.no_backup and os.path.exists(args.db):
        backup = f"{args.db}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(args.db, backup)
        print(f"[..] 已备份 -> {backup}")
    return run(args.db, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
