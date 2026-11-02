"""
建表脚本：展商名录 / 展品库（catalog_exhibitors / catalog_products）

背景
----
平台新增「展商名录 / 展品库」只读目录模块，数据来自**第三方公开名录导入**
（约 3.1 万展商 / 7 万展品，信息快照，不是平台账号），因此单独建两张表。
模型定义见 `app/models/catalog.py`。

本脚本只做两件事，**不改任何既有表**：
    1. CREATE TABLE IF NOT EXISTS  catalog_exhibitors / catalog_products
    2. CREATE INDEX IF NOT EXISTS   模型里声明的索引 + 两个唯一约束已内联在表 DDL 中

幂等：重复执行安全（表/索引已存在则跳过并打印提示），不做 DROP、不做 ALTER、
不写业务数据、不备份（因为不触碰既有表）。

用法（在 `expohub-backend/` 或仓库根目录执行都可以）
----
    python scripts/migrate_catalog_tables.py --dry-run     # 只打印将要执行的 SQL
    python scripts/migrate_catalog_tables.py               # 真正建表
    python scripts/migrate_catalog_tables.py --db path/to/expohub.db

注意
----
- 仅支持 SQLite（项目开发库默认 sqlite:///./expohub.db）。生产 MySQL 请按同样
  字段顺序用 DDL 迁移；SQL 已尽量写成两种数据库都认的写法，但脚本本身只连 SQLite。
- 应用启动时 `Base.metadata.create_all` 也会建这两张表（模型已注册到
  app/models/__init__.py 与 app/main.py）。本脚本适用于"不想重启服务"的场景
  ——两者 DDL 完全一致（下面的 SQL 就是由 SQLAlchemy 模型编译出来的）。
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from typing import Dict, List

# ============================================================
# DDL（由 app/models/catalog.py 用 SQLite 方言编译生成，保持逐字一致）
# ============================================================

DDL_TABLES: Dict[str, str] = {
    "catalog_exhibitors": """
CREATE TABLE IF NOT EXISTS catalog_exhibitors (
	id INTEGER NOT NULL,
	name VARCHAR(255) NOT NULL,
	name_en VARCHAR(255),
	expo_name VARCHAR(255),
	exhibition_id INTEGER,
	industry VARCHAR(255),
	city VARCHAR(100),
	country VARCHAR(100),
	booth_no VARCHAR(64),
	company_type VARCHAR(64),
	scale VARCHAR(64),
	main_business TEXT,
	website VARCHAR(512),
	product_count INTEGER DEFAULT 0 NOT NULL,
	description TEXT,
	source VARCHAR(255),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT uq_catalog_exhibitor UNIQUE (expo_name, name),
	FOREIGN KEY(exhibition_id) REFERENCES exhibitions (id)
)
""",
    "catalog_products": """
CREATE TABLE IF NOT EXISTS catalog_products (
	id INTEGER NOT NULL,
	name VARCHAR(255) NOT NULL,
	category VARCHAR(255),
	application VARCHAR(255),
	price_spec VARCHAR(255),
	image VARCHAR(512),
	detail_html TEXT,
	exhibitor_name VARCHAR(255),
	exhibitor_id INTEGER,
	expo_name VARCHAR(255),
	booth_no VARCHAR(64),
	source VARCHAR(255),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT uq_catalog_product UNIQUE (expo_name, exhibitor_name, name),
	FOREIGN KEY(exhibitor_id) REFERENCES catalog_exhibitors (id)
)
""",
}

DDL_INDEXES: Dict[str, str] = {
    # ---- catalog_exhibitors ----
    "ix_catalog_exhibitors_name": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_exhibitors_name "
        "ON catalog_exhibitors (name)"
    ),
    "ix_catalog_exhibitors_expo_name": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_exhibitors_expo_name "
        "ON catalog_exhibitors (expo_name)"
    ),
    "ix_catalog_exhibitors_exhibition_id": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_exhibitors_exhibition_id "
        "ON catalog_exhibitors (exhibition_id)"
    ),
    "ix_catalog_exhibitors_industry": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_exhibitors_industry "
        "ON catalog_exhibitors (industry)"
    ),
    "ix_catalog_exhibitors_city": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_exhibitors_city "
        "ON catalog_exhibitors (city)"
    ),
    # ---- catalog_products ----
    "ix_catalog_products_name": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_products_name "
        "ON catalog_products (name)"
    ),
    "ix_catalog_products_category": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_products_category "
        "ON catalog_products (category)"
    ),
    "ix_catalog_products_exhibitor_name": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_products_exhibitor_name "
        "ON catalog_products (exhibitor_name)"
    ),
    "ix_catalog_products_exhibitor_id": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_products_exhibitor_id "
        "ON catalog_products (exhibitor_id)"
    ),
    "ix_catalog_products_expo_name": (
        "CREATE INDEX IF NOT EXISTS ix_catalog_products_expo_name "
        "ON catalog_products (expo_name)"
    ),
}

# 这两张表由本脚本负责；其它表一律不碰
OWN_TABLES = tuple(DDL_TABLES.keys())


# ============================================================
# 默认数据库路径 / 参数
# ============================================================

def default_db_path() -> str:
    """默认库：环境变量 EXPOHUB_DB > <expohub-backend>/expohub.db"""
    env = os.environ.get("EXPOHUB_DB") or os.environ.get("DATABASE_PATH")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))       # expohub-backend/scripts
    return os.path.join(os.path.dirname(here), "expohub.db")


def _tables(cur: sqlite3.Cursor) -> List[str]:
    return [
        row[0]
        for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]


def _indexes(cur: sqlite3.Cursor) -> List[str]:
    return [
        row[0]
        for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    ]


def _count(conn: sqlite3.Connection, table: str, exists: bool) -> int:
    if not exists:
        return 0
    return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


# ============================================================
# 主流程
# ============================================================

def run(db_path: str, dry_run: bool) -> int:
    if not os.path.isfile(db_path):
        print(f"[XX] 数据库文件不存在：{db_path}")
        return 1

    print(f"[--] 目标库：{os.path.abspath(db_path)}")
    print(f"[--] 模式：{'DRY-RUN（只打印，不执行）' if dry_run else '实际执行'}")

    conn = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    try:
        cur = conn.cursor()
        tables_before = _tables(cur)
        indexes_before = _indexes(cur)
        print(f"[--] 现有表 {len(tables_before)} 张；现有索引 {len(indexes_before)} 个")

        # 外键目标表提醒（本脚本不建 exhibitions）
        if "exhibitions" not in tables_before:
            print("[!!] 提示：未找到 exhibitions 表（catalog_exhibitors.exhibition_id 的"
                  "外键目标）。先跑应用建表，或忽略此提示（该列为可空，不影响本表使用）。")

        rows_before = {
            t: _count(conn, t, t in tables_before) for t in OWN_TABLES
        }

        created_tables: List[str] = []
        skipped_tables: List[str] = []
        created_indexes: List[str] = []
        skipped_indexes: List[str] = []

        # ---- 1) 建表（只 CREATE TABLE IF NOT EXISTS）----
        for table, ddl in DDL_TABLES.items():
            if table in tables_before:
                skipped_tables.append(table)
                print(f"[--] 表已存在，跳过：{table}")
                continue
            if dry_run:
                print(ddl.strip() + ";")
                created_tables.append(table)
                continue
            cur.execute(ddl)
            created_tables.append(table)
            print(f"[OK] 建表：{table}")

        # ---- 2) 建索引（表已存在时仍补齐缺失索引）----
        for index_name, ddl in DDL_INDEXES.items():
            if index_name in indexes_before:
                skipped_indexes.append(index_name)
                continue
            if dry_run:
                print(ddl + ";")
                created_indexes.append(index_name)
                continue
            cur.execute(ddl)
            created_indexes.append(index_name)
            print(f"[OK] 建索引：{index_name}")

        if not dry_run:
            conn.commit()

        # ---- 3) 结果核对（再读一次 sqlite_master，证明落库成功）----
        tables_after = _tables(cur)
        indexes_after = _indexes(cur)
        rows_after = {
            t: _count(conn, t, t in tables_after) for t in OWN_TABLES
        }

        print("")
        print("[==] 汇总")
        print(f"     新建表 {len(created_tables)} 张"
              f"{('：' + ', '.join(created_tables)) if created_tables else ''}")
        print(f"     跳过表 {len(skipped_tables)} 张"
              f"{('：' + ', '.join(skipped_tables)) if skipped_tables else ''}")
        print(f"     新建索引 {len(created_indexes)} 个"
              f"{('：' + ', '.join(created_indexes)) if created_indexes else ''}")
        print(f"     已存在索引 {len(skipped_indexes)} 个")
        for table in OWN_TABLES:
            if table not in tables_after:
                print(f"     [!!] {table} 仍不存在"
                      f"{'（DRY-RUN 未执行，属正常）' if dry_run else ''}")
                continue
            cols = [row[1] for row in cur.execute(f'PRAGMA table_info("{table}")')]
            idx = [row[1] for row in cur.execute(f'PRAGMA index_list("{table}")')]
            print(f"     {table}: {len(cols)} 列 {cols}")
            print(f"     {table}: {len(idx)} 个索引 {sorted(idx)}")
            print(f"     {table}: 行数 {rows_before[table]} -> {rows_after[table]}"
                  f"（脚本不写数据）")

        # 保护性断言：只允许出现我们自己的两张表是新增的
        new_tables = [t for t in tables_after if t not in tables_before]
        unexpected = [t for t in new_tables if t not in OWN_TABLES]
        if unexpected:
            print(f"[XX] 意外新建了非本脚本的表：{unexpected}")
            return 2

        if dry_run:
            print("")
            print("[--] DRY-RUN 结束，未改动数据库。去掉 --dry-run 即可执行。")
        else:
            print("")
            print("[OK] 完成。若应用正在运行，无需重启（模型已在启动时注册；"
                  "本脚本已建好表）。")
        return 0
    finally:
        conn.close()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="幂等建表：catalog_exhibitors / catalog_products（只 CREATE TABLE/INDEX IF NOT EXISTS）"
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
