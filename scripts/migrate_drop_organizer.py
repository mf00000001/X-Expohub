"""把 ExpoHub 从「四方撮合」迁移到「两方撮合」（2026-10-19 决策）

做三件事，全部幂等、可重复执行：

1. users 表补 `region` 列（模型早已有该字段但 SQLite 库缺列，导致
   `GET /exhibitions/{id}/exhibitors` 读 `u.region` 直接 500）
2. 存量 `role='organizer'` 账号升级为 `role='admin'`
   （主办方角色已取消；账号本身保留，作为平台运营子账号）
3. 展会的 `organizer_id` 归一到管理员账号，`organizer_name` 统一为「平台运营」

用法：
    # 预演（只打印将要做什么，不写库）
    python scripts/migrate_drop_organizer.py --dry-run

    # 执行（默认库：expohub-backend/expohub.db）
    python scripts/migrate_drop_organizer.py

    # 指定库 / 指定管理员账号
    python scripts/migrate_drop_organizer.py --db expohub-backend/expohub.db --admin-id 1
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DEFAULT_DB = os.path.join("expohub-backend", "expohub.db")
PLATFORM_OPERATOR_NAME = "平台运营"


def table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    return [row[1] for row in cur.execute(f'PRAGMA table_info("{table}")')]


def run(db_path: str, dry_run: bool, admin_id: int | None) -> int:
    if not os.path.exists(db_path):
        print(f"[XX] 数据库不存在：{db_path}")
        return 1

    conn = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")

    actions: list[str] = []

    # ---------- 1. region 列 ----------
    cols = table_columns(cur, "users")
    if "region" not in cols:
        actions.append("users: 新增列 region VARCHAR(50)")
        if not dry_run:
            cur.execute("ALTER TABLE users ADD COLUMN region VARCHAR(50)")
    else:
        print("[--] users.region 已存在")

    # ---------- 2. organizer -> admin ----------
    organizers = list(cur.execute(
        "SELECT id, username, email, company_name FROM users WHERE role='organizer'"
    ))
    if organizers:
        for o in organizers:
            actions.append(f"users: {o['username']}(id={o['id']}) organizer -> admin")
        if not dry_run:
            cur.execute("UPDATE users SET role='admin' WHERE role='organizer'")
    else:
        print("[--] 没有 role='organizer' 的账号")

    # 选管理员：显式传入 > 最早创建的 admin
    if admin_id is None:
        row = cur.execute(
            "SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1"
        ).fetchone()
        admin_id = row["id"] if row else None
    if admin_id is None:
        print("[!!] 库里没有任何 admin 账号，展会不会被重新归属（展商/买家不受影响）")
    else:
        print(f"[..] 展会归属管理员 id={admin_id}")

        # ---------- 3. 展会归属归一 ----------
        orphan = cur.execute(
            "SELECT COUNT(*) AS n FROM exhibitions WHERE organizer_id IS NULL OR organizer_id <> ?",
            (admin_id,),
        ).fetchone()["n"]
        if orphan:
            actions.append(f"exhibitions: {orphan} 场展会的 organizer_id/organizer_name 归一到管理员")
            if not dry_run:
                cur.execute(
                    "UPDATE exhibitions SET organizer_id=?, organizer_name=? "
                    "WHERE organizer_id IS NULL OR organizer_id <> ?",
                    (admin_id, PLATFORM_OPERATOR_NAME, admin_id),
                )
        else:
            print("[--] 展会归属已是管理员")

        if not dry_run:
            cur.execute(
                "UPDATE exhibitions SET organizer_name=? WHERE organizer_name IS NULL OR organizer_name=''",
                (PLATFORM_OPERATOR_NAME,),
            )

    if dry_run:
        print("\n=== DRY-RUN：以下 %d 项本会执行 ===" % len(actions))
        for a in actions:
            print("  -", a)
        conn.close()
        return 0

    conn.commit()

    # 自检
    left = cur.execute("SELECT COUNT(*) AS n FROM users WHERE role='organizer'").fetchone()["n"]
    print("\n=== 迁移完成 ===")
    for a in actions:
        print("  [OK]", a)
    print(f"  剩余 organizer 账号：{left}")
    print(f"  用户角色分布：{ {r['role']: r['n'] for r in cur.execute('SELECT role, COUNT(*) AS n FROM users GROUP BY role')} }")
    conn.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ExpoHub：移除主办方角色（两方撮合迁移）")
    ap.add_argument("--db", default=DEFAULT_DB, help="SQLite 库路径（默认 expohub-backend/expohub.db）")
    ap.add_argument("--admin-id", type=int, default=None, help="指定承接展会归属的管理员 id")
    ap.add_argument("--dry-run", action="store_true", help="只预演，不写库")
    ap.add_argument("--no-backup", action="store_true", help="跳过自动备份（默认会在同目录生成 .bak-时间戳）")
    args = ap.parse_args()

    if not args.dry_run and not args.no_backup and os.path.exists(args.db):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{args.db}.bak-{stamp}"
        shutil.copy2(args.db, backup)
        print(f"[..] 已备份数据库 -> {backup}")

    return run(args.db, args.dry_run, args.admin_id)


if __name__ == "__main__":
    sys.exit(main())
