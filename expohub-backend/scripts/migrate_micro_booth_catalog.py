#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""迁移脚本：给 micro_booths 加 `catalog_exhibitor_id`（名录展商ID）+ 索引

背景
----
微展位的数据源要从 seed 假数据换成**真实展商名录**（catalog_exhibitors / catalog_products）。
名录展商不是平台账号，微展位表却要求 `exhibitor_id` 非空（FK users.id），所以新增一列
`catalog_exhibitor_id`（可空，FK catalog_exhibitors.id）标识「这条微展位来自哪家名录展商」，
`exhibitor_id` 统一指向一个目录占位账号（由 fill_micro_booths_from_catalog.py 创建/复用）。

本脚本只做两件事，**不改任何其它表/列**：
    1. ALTER TABLE micro_booths ADD COLUMN catalog_exhibitor_id INTEGER
       REFERENCES catalog_exhibitors (id)              -- 可空，默认 NULL
    2. CREATE INDEX IF NOT EXISTS ix_micro_booths_catalog_exhibitor_id
       ON micro_booths (catalog_exhibitor_id)

幂等
----
- 列已存在 → 跳过 ALTER（打印提示），不会重复加列；
- 索引已存在 → 跳过创建；
- 重复执行安全，不 DROP、不写业务数据（脚本末尾核对 micro_booths 行数前后不变）。

SQLite 注意
-----------
`ALTER TABLE ... ADD COLUMN` 加带 REFERENCES 的列时，该列默认值必须为 NULL
（本列正是可空无默认值），因此在 `PRAGMA foreign_keys=ON` 的库上也能执行。
SQLite 没有 "ADD CONSTRAINT"，外键只能随列定义一起加进表 DDL —— 这正是本脚本的写法。

用法（在 `expohub-backend/` 或仓库根目录执行都可以）
----
    python scripts/migrate_micro_booth_catalog.py --dry-run   # 只打印将执行的 SQL
    python scripts/migrate_micro_booth_catalog.py             # 真正加列 + 建索引
    python scripts/migrate_micro_booth_catalog.py --db path/to/expohub.db

执行顺序
--------
    migrate_catalog_tables.py        （建 catalog 两张表，若尚未建）
    migrate_micro_booth_catalog.py   （本脚本：微展位加列 + 索引）
    fill_micro_booths_from_catalog.py --apply --reset --force   （灌数据，默认 dry-run）
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from typing import List

# ============================================================
# DDL
# ============================================================

TABLE = "micro_booths"
FK_TABLE = "catalog_exhibitors"
COLUMN = "catalog_exhibitor_id"
INDEX_NAME = f"ix_{TABLE}_{COLUMN}"

DDL_ADD_COLUMN = (
    f'ALTER TABLE "{TABLE}" ADD COLUMN "{COLUMN}" INTEGER '
    f'REFERENCES "{FK_TABLE}" (id)'
)
DDL_CREATE_INDEX = (
    f'CREATE INDEX IF NOT EXISTS "{INDEX_NAME}" ON "{TABLE}" ("{COLUMN}")'
)


# ============================================================
# 默认数据库路径 / 参数
# ============================================================

def default_db_path() -> str:
    """默认库：环境变量 EXPOHUB_DB > <expohub-backend>/expohub.db（用 __file__ 定位）"""
    env = os.environ.get("EXPOHUB_DB") or os.environ.get("DATABASE_PATH")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))          # expohub-backend/scripts
    return os.path.join(os.path.dirname(here), "expohub.db")


# ============================================================
# 小工具
# ============================================================

def _tables(cur: sqlite3.Cursor) -> List[str]:
    return [
        row[0]
        for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]


def _columns(cur: sqlite3.Cursor, table: str) -> List[str]:
    return [row[1] for row in cur.execute(f'PRAGMA table_info("{table}")')]


def _indexes(cur: sqlite3.Cursor, table: str) -> List[str]:
    return [row[1] for row in cur.execute(f'PRAGMA index_list("{table}")')]


def _row_count(cur: sqlite3.Cursor, table: str) -> int:
    return cur.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def _foreign_keys(cur: sqlite3.Cursor, table: str) -> List[tuple]:
    return list(cur.execute(f'PRAGMA foreign_key_list("{table}")'))


# ============================================================
# 主流程
# ============================================================

def run(db_path: str, dry_run: bool) -> int:
    if not os.path.isfile(db_path):
        print(f"[XX] 数据库文件不存在：{db_path}")
        return 1

    print(f"[--] 目标库：{os.path.abspath(db_path)}")
    print(f"[--] 模式：{'DRY-RUN（只打印，不执行）' if dry_run else '实际执行'}")

    # dry-run 用只读连接，从物理上保证不会写库
    if dry_run:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)

    try:
        cur = conn.cursor()
        tables = _tables(cur)

        # ---- 0) 前置检查：两张表必须存在 ----
        if TABLE not in tables:
            print(f"[XX] 未找到表 {TABLE}（先启动一次应用让它 create_all，或先跑建表脚本）")
            return 1
        if FK_TABLE not in tables:
            print(f"[XX] 未找到外键目标表 {FK_TABLE}，请先执行："
                  f" python scripts/migrate_catalog_tables.py")
            return 1

        rows_before = _row_count(cur, TABLE)
        cols_before = _columns(cur, TABLE)
        idx_before = _indexes(cur, TABLE)
        print(f"[--] {TABLE}：{rows_before} 行，{len(cols_before)} 列，{len(idx_before)} 个索引")
        if COLUMN in cols_before:
            print(f"[--] 列已存在，跳过 ALTER：{COLUMN}")
        else:
            if dry_run:
                print(DDL_ADD_COLUMN + ";")
            else:
                cur.execute(DDL_ADD_COLUMN)
                print(f"[OK] 加列：{TABLE}.{COLUMN}")

        if INDEX_NAME in idx_before:
            print(f"[--] 索引已存在，跳过创建：{INDEX_NAME}")
        else:
            if dry_run:
                print(DDL_CREATE_INDEX + ";")
            else:
                cur.execute(DDL_CREATE_INDEX)
                print(f"[OK] 建索引：{INDEX_NAME}")

        if not dry_run:
            conn.commit()

        # ---- 1) 复核：再读一次 schema（证明确实落库）----
        cols_after = _columns(cur, TABLE)
        idx_after = _indexes(cur, TABLE)
        rows_after = _row_count(cur, TABLE)
        fks = _foreign_keys(cur, TABLE)

        print("")
        print("[==] 汇总")
        print(f"     {TABLE} 列：{len(cols_before)} -> {len(cols_after)}")
        if COLUMN in cols_after:
            print(f"     已存在列：{COLUMN}")
        else:
            print(f"     [!!] 列仍不存在：{COLUMN}"
                  f"{'（DRY-RUN 未执行，属正常）' if dry_run else ''}")
        print(f"     {TABLE} 索引：{sorted(set(idx_after))}")
        print(f"     {TABLE} 外键：{[(fk[2], fk[3], fk[4]) for fk in fks]}")
        print(f"     {TABLE} 行数：{rows_before} -> {rows_after}"
              f"（本脚本不写数据，{'未改动' if rows_before == rows_after else '异常变化！'}）")

        # 保护性断言：本脚本只允许改动 micro_booths 的 schema，行数必须不变
        if rows_before != rows_after:
            print("[XX] micro_booths 行数发生变化，脚本行为异常，请检查！")
            return 2

        if dry_run:
            print("")
            print("[--] DRY-RUN 结束，未改动数据库。去掉 --dry-run 即可执行。")
        else:
            print("")
            print("[OK] 完成。应用已启动时无需重启：ORM 查询按需读该列，"
                  "下次请求即可命中。")
        return 0
    finally:
        conn.close()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="幂等迁移：micro_booths 加 catalog_exhibitor_id 列 + 索引"
    )
    parser.add_argument(
        "--db", default=default_db_path(),
        help="SQLite 数据库路径（默认：<expohub-backend>/expohub.db，可用 EXPOHUB_DB 覆盖）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印 SQL，不执行")
    args = parser.parse_args(argv)
    return run(args.db, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
