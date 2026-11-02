"""
建表脚本：参展关系表 `exhibition_exhibitors`（展会 ↔ 名录展商，多对多）

背景
----
旧模型是「弱三层」：`catalog_exhibitors.exhibition_id` 只有 48.8% 有值
（15,585 / 31,938 为 NULL），展会详情页靠 `expo_name` 字符串别名硬凑；且同一
展商字段只能挂一个 exhibition_id，参加多场 / 多届时被压成一条。

新模型用一张关系表把「某展商参加了某届展会」显式化：
    exhibitions 1 ──< exhibition_exhibitors >── 1 catalog_exhibitors ──< catalog_products
模型定义见 `app/models/exhibition_exhibitor.py`。

本脚本只做两件事，**不改任何既有表**、不写业务数据、不删列：
    1. CREATE TABLE IF NOT EXISTS  exhibition_exhibitors
    2. CREATE INDEX  IF NOT EXISTS  exhibition_id / catalog_exhibitor_id 两列

幂等：重复执行安全（表/索引已存在则跳过并打印提示）。回填数据由
`scripts/backfill_exhibition_exhibitors.py` 负责（它会先备份 DB）。

用法（在 `expohub-backend/` 或仓库根目录执行都可以）
----
    python scripts/migrate_exhibition_exhibitors.py --dry-run     # 只打印将要执行的 SQL
    python scripts/migrate_exhibition_exhibitors.py               # 真正建表
    python scripts/migrate_exhibition_exhibitors.py --db path/to/expohub.db

注意
----
- 仅支持 SQLite（开发库默认 sqlite:///./expohub.db）。生产 MySQL 请按同样字段顺序
  用等价 DDL 迁移；脚本本身只连 SQLite。
- 应用启动时 `Base.metadata.create_all` 也会建这张表（模型已在
  app/models/__init__.py 与 app/main.py 注册），两者 DDL 完全一致
  ——脚本末尾会用 SQLAlchemy 模型重新编译一次 DDL 做自检。
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from typing import Dict, List

# ============================================================
# DDL（由 app/models/exhibition_exhibitor.py 用 SQLite 方言编译生成）
# ============================================================

TABLE = "exhibition_exhibitors"

DDL_TABLE = """
CREATE TABLE IF NOT EXISTS exhibition_exhibitors (
	id INTEGER NOT NULL,
	exhibition_id INTEGER NOT NULL,
	catalog_exhibitor_id INTEGER NOT NULL,
	expo_label VARCHAR(255),
	booth_no VARCHAR(64),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT uq_exhibition_exhibitor UNIQUE (exhibition_id, catalog_exhibitor_id),
	FOREIGN KEY(exhibition_id) REFERENCES exhibitions (id),
	FOREIGN KEY(catalog_exhibitor_id) REFERENCES catalog_exhibitors (id)
)
"""

DDL_INDEXES: Dict[str, str] = {
    "ix_exhibition_exhibitors_exhibition_id": (
        "CREATE INDEX IF NOT EXISTS ix_exhibition_exhibitors_exhibition_id "
        "ON exhibition_exhibitors (exhibition_id)"
    ),
    "ix_exhibition_exhibitors_catalog_exhibitor_id": (
        "CREATE INDEX IF NOT EXISTS ix_exhibition_exhibitors_catalog_exhibitor_id "
        "ON exhibition_exhibitors (catalog_exhibitor_id)"
    ),
}

# 外键目标表：本脚本不建它们，只做存在性提醒
FK_TARGETS = ("exhibitions", "catalog_exhibitors")


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


def _norm_sql(sql: str) -> str:
    """把 DDL 压成可比较的规范形式（忽略空白/大小写/IF NOT EXISTS）。"""
    s = re.sub(r"\s+", " ", sql).strip().lower()
    s = s.replace("if not exists ", "")
    s = re.sub(r"\s*([(),])\s*", r"\1", s)
    return s.replace(" ;", "")


def _model_ddl() -> tuple[str, list[str]]:
    """用 SQLAlchemy 模型重新编译 DDL（自检用；不连库）。"""
    from sqlalchemy.dialects import sqlite
    from sqlalchemy.schema import CreateIndex, CreateTable

    from app.models.exhibition_exhibitor import ExhibitionExhibitor

    table_ddl = str(
        CreateTable(ExhibitionExhibitor.__table__).compile(dialect=sqlite.dialect())
    )
    index_ddl = [
        str(CreateIndex(i).compile(dialect=sqlite.dialect()))
        for i in sorted(ExhibitionExhibitor.__table__.indexes, key=lambda x: x.name)
    ]
    return table_ddl, index_ddl


def _self_check() -> int:
    """模型 ↔ 本脚本 DDL 一致性自检。返回不一致项数量。"""
    try:
        from app.models.exhibition_exhibitor import ExhibitionExhibitor  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        print(f"[!!] 跳过 DDL 自检（导入模型失败，请确认在 expohub-backend/ 下执行）：{exc}")
        return 0

    table_ddl, index_ddl = _model_ddl()
    bad = 0
    if _norm_sql(table_ddl) != _norm_sql(DDL_TABLE):
        bad += 1
        print("[XX] 表 DDL 与模型不一致：")
        print("     脚本:", _norm_sql(DDL_TABLE))
        print("     模型:", _norm_sql(table_ddl))
    script_idx = {_norm_sql(v) for v in DDL_INDEXES.values()}
    model_idx = {_norm_sql(v) for v in index_ddl}
    if script_idx != model_idx:
        bad += 1
        print("[XX] 索引 DDL 与模型不一致：")
        print("     脚本:", sorted(script_idx))
        print("     模型:", sorted(model_idx))
    if not bad:
        print("[OK] DDL 自检：脚本 DDL 与 app/models/exhibition_exhibitor.py 完全一致")
    return bad


# ============================================================
# 主流程
# ============================================================

def run(db_path: str, dry_run: bool) -> int:
    if not os.path.isfile(db_path):
        print(f"[XX] 数据库文件不存在：{db_path}")
        return 1

    print(f"[--] 目标库：{os.path.abspath(db_path)}")
    print(f"[--] 模式：{'DRY-RUN（只打印，不执行）' if dry_run else '实际执行'}")
    print(f"[--] 表：{TABLE}（唯一约束 uq_exhibition_exhibitor + 2 个索引）")

    conn = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    try:
        cur = conn.cursor()
        tables_before = _tables(cur)
        indexes_before = _indexes(cur)
        print(f"[--] 现有表 {len(tables_before)} 张；现有索引 {len(indexes_before)} 个")

        missing_fk = [t for t in FK_TARGETS if t not in tables_before]
        if missing_fk:
            print(f"[!!] 提示：外键目标表缺失 {missing_fk}。"
                  f"先跑应用建表（Base.metadata.create_all），或忽略此提示"
                  f"（本表建得出来，但外键约束会指向不存在的表）。")

        rows_before = 0
        if TABLE in tables_before:
            rows_before = cur.execute(
                f'SELECT COUNT(*) FROM "{TABLE}"'
            ).fetchone()[0]
            print(f"[--] 表已存在，跳过建表（现有 {rows_before} 行）")

        # ---- 1) 建表 ----
        created_table = False
        if TABLE not in tables_before:
            if dry_run:
                print(DDL_TABLE.strip() + ";")
            else:
                cur.execute(DDL_TABLE)
                print(f"[OK] 建表：{TABLE}")
            created_table = True

        # ---- 2) 建索引（表已存在时也补齐缺失索引）----
        created_indexes: List[str] = []
        for name, ddl in DDL_INDEXES.items():
            if name in indexes_before:
                continue
            if dry_run:
                print(ddl + ";")
            else:
                cur.execute(ddl)
                print(f"[OK] 建索引：{name}")
            created_indexes.append(name)

        if not dry_run:
            conn.commit()

        # ---- 3) 结果核对（再读 sqlite_master，证明落库成功）----
        tables_after = _tables(cur)
        indexes_after = _indexes(cur)
        rows_after = 0
        if TABLE in tables_after:
            rows_after = cur.execute(f'SELECT COUNT(*) FROM "{TABLE}"').fetchone()[0]

        print("")
        print("[==] 汇总")
        print(f"     建表：{'是' if created_table else '否（已存在）'}")
        print(f"     新建索引 {len(created_indexes)} 个"
              f"{('：' + ', '.join(created_indexes)) if created_indexes else ''}")
        if TABLE not in tables_after:
            print(f"     [!!] {TABLE} 仍不存在"
                  f"{'（DRY-RUN 未执行，属正常）' if dry_run else ''}")
        else:
            cols = [row[1] for row in cur.execute(f'PRAGMA table_info("{TABLE}")')]
            idx = [row[1] for row in cur.execute(f'PRAGMA index_list("{TABLE}")')]
            fks = [
                (row[2], row[3], row[4])
                for row in cur.execute(f'PRAGMA foreign_key_list("{TABLE}")')
            ]
            print(f"     {TABLE}: {len(cols)} 列 {cols}")
            print(f"     {TABLE}: {len(idx)} 个索引 {sorted(idx)}")
            print(f"     {TABLE}: 外键 {sorted(fks)}")
            print(f"     {TABLE}: 行数 {rows_before} -> {rows_after}（本脚本不写数据）")

        # 保护性断言：只允许本表是新增的
        new_tables = [t for t in tables_after if t not in tables_before]
        unexpected = [t for t in new_tables if t != TABLE]
        if unexpected:
            print(f"[XX] 意外新建了非本脚本的表：{unexpected}")
            return 2

        print("")
        bad = _self_check()
        if bad:
            return 3

        if dry_run:
            print("")
            print("[--] DRY-RUN 结束，未改动数据库。去掉 --dry-run 即可执行。")
        else:
            print("")
            print("[OK] 完成。下一步：python scripts/backfill_exhibition_exhibitors.py"
                  "（默认 dry-run，加 --apply 才会写数据，写前自动备份）")
        return 0
    finally:
        conn.close()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="幂等建表：exhibition_exhibitors（只 CREATE TABLE/INDEX IF NOT EXISTS）"
    )
    parser.add_argument(
        "--db", default=default_db_path(),
        help="SQLite 数据库路径（默认：<expohub-backend>/expohub.db，可用 EXPOHUB_DB 覆盖）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印 SQL，不执行")
    args = parser.parse_args(argv)
    return run(args.db, args.dry_run)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
