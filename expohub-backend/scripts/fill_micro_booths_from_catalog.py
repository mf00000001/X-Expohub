#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""用**真实展商名录**填充 micro_booths（清掉 seed 假数据），默认 dry-run

背景
----
`micro_booths` 原本是 seed 造的 1001 条假数据（名称如「永泰科技-电子及家电」），
并带编造的浏览/收藏统计（sum(view_count)=248851、sum(favorite_count)=15070）。
现在数据源换成 `catalog_exhibitors` / `catalog_products`（第三方公开名录快照），
本脚本负责把名录展商灌成微展位。

口径（不造任何数字）
----
- `exhibitor_id`  → 名录归属账号（username=`catalog_import`，由本脚本找或建）
- `catalog_exhibitor_id` → 名录展商 id（**幂等唯一键**，已存在就更新，不重复插入）
- `name` / `description` / `industry_domain` → 名录原文字段（截断到列宽）
- `logo_url` = NULL、`membership_tier` = 'free'（不按数据量臆造付费档位）
- `view_count` / `search_appearances` / `favorite_count` = **0**（真实统计由真实访问产生）
- `status` = 'active'、`exhibition_id` = 名录已对齐的展会 id（为空则 NULL）

参数
----
    --db PATH     默认 <expohub-backend>/expohub.db（用 __file__ 定位）
    --limit N     取 product_count 最高的前 N 家名录展商，默认 5000
    --apply       默认 dry-run（只打印，不写库）；加 --apply 才真正写
    --dry-run     显式声明 dry-run（与默认行为相同，便于脚本里写明意图）
    --reset       删除现有 micro_booths 全部行（默认不删）
    --force       即使 favorites/appointments 引用了微展位也允许 --reset 删除

安全
----
- `--reset` 前先检查引用：`favorites(entity_type='micro_booth')` 与 `appointments`
  （若该表存在指向微展位的列）。有引用则**打印警告并拒绝删除**，除非追加 --force；
- 删除微展位前先把 `products.micro_booth_id` 置空（保留展商自己的展品，只断开挂载）；
- dry-run 用只读连接（`mode=ro`），物理上不可能写库；
- 全程单事务（`BEGIN IMMEDIATE`），失败自动回滚。

用法
----
    # 0) 先加列（另一个脚本，幂等）
    python scripts/migrate_micro_booth_catalog.py

    # 1) 预演（真实库此时还没有 catalog_exhibitor_id 列，会提示先跑迁移脚本）
    python scripts/fill_micro_booths_from_catalog.py --dry-run --limit 5000

    # 2) 在副本库上试跑（绝不写真实库）
    copy expohub.db %TEMP%\\expohub_copy.db
    python scripts/fill_micro_booths_from_catalog.py --db %TEMP%\\expohub_copy.db --apply --reset --force --limit 200

    # 3) 正式执行（由负责人统一执行）
    python scripts/fill_micro_booths_from_catalog.py --apply --reset --force
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from typing import Dict, List, Optional, Sequence, Tuple

# ============================================================
# 常量
# ============================================================

TABLE = "micro_booths"
CATALOG_TABLE = "catalog_exhibitors"
USERS_TABLE = "users"

# 名录归属账号（占位账号：只用来满足 micro_booths.exhibitor_id 的非空外键）
ACCOUNT_USERNAME = "catalog_import"
ACCOUNT_EMAIL = "catalog-import@expohub.local"
ACCOUNT_COMPANY = "展商名录（系统占位账号，不可登录）"
# 不可用哈希：不是合法 bcrypt 串，security.verify_password 会捕获 ValueError 返回 False，
# 因此该账号任何密码都登录不上；这里**不生成可猜密码**。
ACCOUNT_PASSWORD_HASH = "!"

# 字段截断（与模型列宽一致）
NAME_MAX = 200          # micro_booths.name VARCHAR(200)
DESC_MAX = 500          # micro_booths.description TEXT（按需求截 500 字）
MAIN_BIZ_MAX = 200      # description 为空时用 main_business 前 200 字
INDUSTRY_MAX = 100      # micro_booths.industry_domain VARCHAR(100)

DEFAULT_LIMIT = 5000
CHUNK = 500             # IN 查询分批（兼容 SQLite 旧版 999 变量上限）

# 退出码
RC_OK = 0
RC_MISSING = 1          # 库/表/列缺失
RC_SCHEMA = 2           # schema 不对（缺 catalog_exhibitor_id 列）
RC_REFUSED = 3          # 有引用，拒绝删除


# ============================================================
# 通用小工具
# ============================================================

def harden_stdout() -> None:
    """重定向输出时强制 UTF-8，避免 Windows 控制台 cp936 把中文打成乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def default_db_path() -> str:
    """默认库：环境变量 EXPOHUB_DB > <expohub-backend>/expohub.db（用 __file__ 定位）"""
    env = os.environ.get("EXPOHUB_DB") or os.environ.get("DATABASE_PATH")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))          # expohub-backend/scripts
    return os.path.join(os.path.dirname(here), "expohub.db")


def _clean(value) -> Optional[str]:
    """去首尾空白；None / 空串 / 纯空白 → None（不写空字符串进库）"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truncate(value: Optional[str], limit: int) -> Optional[str]:
    """按字符数截断（SQLite 的 length() 对 TEXT 也按字符计，口径一致）"""
    if value is None:
        return None
    return value[:limit]


def _tables(conn: sqlite3.Connection) -> List[str]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]


def _columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def _sum(conn: sqlite3.Connection, column: str) -> int:
    value = conn.execute(
        f'SELECT COALESCE(SUM("{column}"), 0) FROM "{TABLE}"'
    ).fetchone()[0]
    return int(value or 0)


# ============================================================
# 1) 名录归属账号
# ============================================================

def ensure_account(conn: sqlite3.Connection, apply: bool) -> Tuple[Optional[int], str]:
    """找或建「名录归属账号」，返回 (user_id, 状态描述)

    状态：existing（复用）/ created（已新建）/ would_create（dry-run 将新建）/ none（失败）
    """
    row = conn.execute(
        f'SELECT id, role, status FROM "{USERS_TABLE}" WHERE username = ?',
        (ACCOUNT_USERNAME,),
    ).fetchone()
    if row:
        user_id, role, status = row[0], row[1], row[2]
        print(f"[--] 复用名录归属账号：id={user_id} username={ACCOUNT_USERNAME} "
              f"role={role} status={status}")
        return user_id, "existing"

    # 邮箱被别的用户名占用：不能硬插（users.email 唯一），交人工处理
    clash = conn.execute(
        f'SELECT id, username FROM "{USERS_TABLE}" WHERE email = ?', (ACCOUNT_EMAIL,)
    ).fetchone()
    if clash:
        print(f"[XX] 邮箱 {ACCOUNT_EMAIL} 已被 username={clash[1]}（id={clash[0]}）占用，"
              f"无法创建名录归属账号。请先人工处理该账号（改名/改邮箱）后重跑。")
        return None, "none"

    if not apply:
        print(f"[--] 名录归属账号不存在，--apply 时将创建："
              f"username={ACCOUNT_USERNAME} email={ACCOUNT_EMAIL} "
              f"role=exhibitor status=active password_hash=<不可用>")
        return None, "would_create"

    cur = conn.execute(
        f'INSERT INTO "{USERS_TABLE}" '
        "(username, email, password_hash, role, status, company_name, "
        " is_onboarded, total_points, token_version, personalized_recommend) "
        "VALUES (?, ?, ?, 'exhibitor', 'active', ?, 0, 0, 0, 1)",
        (ACCOUNT_USERNAME, ACCOUNT_EMAIL, ACCOUNT_PASSWORD_HASH, ACCOUNT_COMPANY),
    )
    user_id = int(cur.lastrowid)
    print(f"[OK] 已创建名录归属账号：id={user_id} username={ACCOUNT_USERNAME} "
          f"email={ACCOUNT_EMAIL}（password_hash 不可用，无法登录）")
    return user_id, "created"


# ============================================================
# 2) --reset 前检查引用
# ============================================================

def reference_report(conn: sqlite3.Connection) -> Dict[str, object]:
    """统计有多少行引用了现有 micro_booths

    - favorites：`entity_type='micro_booth' AND entity_id IN (现存的微展位 id)`（真正的引用）
    - appointments：先看该表有没有指向微展位的列（micro_booth_id / booth_id），
      有才算引用；没有则只做信息性统计（关联这些展商账号的预约数，不阻塞删除）
    """
    tables = _tables(conn)
    report: Dict[str, object] = {
        "favorites": 0,
        "appointment_column": None,
        "appointments": 0,
        "appointments_of_booth_owners": 0,
        "has_favorites": "favorites" in tables,
        "has_appointments": "appointments" in tables,
    }

    if report["has_favorites"]:
        report["favorites"] = conn.execute(
            "SELECT COUNT(*) FROM favorites "
            "WHERE entity_type = 'micro_booth' "
            "AND entity_id IN (SELECT id FROM micro_booths)"
        ).fetchone()[0]

    if report["has_appointments"]:
        cols = _columns(conn, "appointments")
        booth_cols = [c for c in ("micro_booth_id", "booth_id") if c in cols]
        if booth_cols:
            column = booth_cols[0]
            report["appointment_column"] = column
            report["appointments"] = conn.execute(
                f'SELECT COUNT(*) FROM appointments WHERE "{column}" '
                f"IN (SELECT id FROM micro_booths)"
            ).fetchone()[0]
        else:
            # appointments 只 FK users.id（没有微展位列）；列出来仅供知情
            report["appointments_of_booth_owners"] = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE exhibitor_id "
                "IN (SELECT DISTINCT exhibitor_id FROM micro_booths "
                "    WHERE exhibitor_id IS NOT NULL)"
            ).fetchone()[0]

    return report


def print_reference_report(report: Dict[str, object]) -> None:
    if report["has_favorites"]:
        print(f"[--] favorites(entity_type='micro_booth') 引用行数：{report['favorites']}")
    else:
        print("[--] 未找到 favorites 表（本库无收藏功能）")

    if not report["has_appointments"]:
        print("[--] 未找到 appointments 表（本库无预约功能）")
    elif report["appointment_column"]:
        print(f"[--] appointments.{report['appointment_column']} 引用行数："
              f"{report['appointments']}")
    else:
        print("[--] appointments 无指向微展位的列（其 exhibitor_id 是 users.id，不是微展位 id）；"
              f"信息性统计：与这些展商账号相关的预约 {report['appointments_of_booth_owners']} 条"
              f"（删除微展位不影响预约行）")


# ============================================================
# 3) 组装待写入数据
# ============================================================

def fetch_catalog_rows(conn: sqlite3.Connection, limit: int) -> List[tuple]:
    """按 product_count DESC, id ASC 取名录展商（与 catalog 列表排序一致）"""
    return list(conn.execute(
        f'SELECT id, name, description, main_business, industry, product_count, '
        f'       exhibition_id '
        f'FROM "{CATALOG_TABLE}" '
        f"ORDER BY product_count DESC, id ASC "
        f"LIMIT ?",
        (limit,),
    ))


def build_payload(rows: Sequence[tuple]) -> Tuple[List[dict], int]:
    """把名录行映射成 micro_booths 字段；返回 (payload, 跳过的空名行数)"""
    payload: List[dict] = []
    skipped = 0
    for cid, name, description, main_business, industry, product_count, exhibition_id in rows:
        clean_name = _truncate(_clean(name), NAME_MAX)
        if not clean_name:
            # 名录没有名字的行不硬造名字，直接跳过（并由调用方打印）
            skipped += 1
            continue
        desc = _truncate(_clean(description), DESC_MAX)
        if desc is None:
            # description 为空 → 用 main_business 前 200 字；都为空 → NULL
            desc = _truncate(_clean(main_business), MAIN_BIZ_MAX)
        payload.append({
            "catalog_exhibitor_id": int(cid),
            "name": clean_name,
            "description": desc,
            "industry_domain": _truncate(_clean(industry), INDUSTRY_MAX),
            "product_count": int(product_count or 0),
            "exhibition_id": exhibition_id,
        })
    return payload, skipped


def existing_booth_map(
    conn: sqlite3.Connection, catalog_ids: Sequence[int]
) -> Dict[int, int]:
    """{catalog_exhibitor_id: micro_booth.id}（分批 IN，幂等 upsert 的依据）"""
    mapping: Dict[int, int] = {}
    ids = list(catalog_ids)
    for start in range(0, len(ids), CHUNK):
        chunk = ids[start:start + CHUNK]
        placeholders = ",".join("?" * len(chunk))
        for cid, booth_id in conn.execute(
            f'SELECT catalog_exhibitor_id, id FROM "{TABLE}" '
            f"WHERE catalog_exhibitor_id IN ({placeholders})",
            chunk,
        ):
            mapping[int(cid)] = int(booth_id)
    return mapping


# ============================================================
# 4) 主流程
# ============================================================

def run(db_path: str, limit: int, apply: bool, reset: bool, force: bool) -> int:
    if not os.path.isfile(db_path):
        print(f"[XX] 数据库文件不存在：{db_path}")
        return RC_MISSING
    if limit <= 0:
        print(f"[XX] --limit 必须为正整数（收到 {limit}）")
        return RC_MISSING

    print(f"[--] 目标库：{os.path.abspath(db_path)}")
    print(f"[--] 模式：{'APPLY（真正写库）' if apply else 'DRY-RUN（只打印，不写库）'}")
    print(f"[--] 参数：limit={limit} reset={reset} force={force}")

    conn = sqlite3.connect(
        f"file:{db_path}?mode={'rw' if apply else 'ro'}", uri=True
    )
    try:
        tables = _tables(conn)
        for needed in (TABLE, USERS_TABLE, CATALOG_TABLE):
            if needed not in tables:
                print(f"[XX] 缺少表 {needed}，请先启动应用建表 / 导入名录")
                return RC_MISSING
        if "catalog_exhibitor_id" not in _columns(conn, TABLE):
            print(f"[XX] {TABLE} 缺少 catalog_exhibitor_id 列，请先执行：")
            print("     python scripts/migrate_micro_booth_catalog.py")
            return RC_SCHEMA

        booths_before = _count(conn, TABLE)
        catalog_total = _count(conn, CATALOG_TABLE)
        print(f"[--] 现有：{TABLE} {booths_before} 行；{CATALOG_TABLE} {catalog_total} 行")
        # 假数据体检（执行前后各打一次，证明没有编造数字残留）
        print(f"[--] 现有微展位统计合计：view_count={_sum(conn, 'view_count')} "
              f"favorite_count={_sum(conn, 'favorite_count')} "
              f"search_appearances={_sum(conn, 'search_appearances')}")

        if apply:
            conn.isolation_level = None            # 手动控制事务
            conn.execute("PRAGMA foreign_keys=ON")  # 与运行时一致，坏外键当场失败
            conn.execute("BEGIN IMMEDIATE")
        try:
            # ---- 1) 名录归属账号 ----
            account_id, account_state = ensure_account(conn, apply)
            if account_state == "none":
                if apply:
                    conn.execute("ROLLBACK")
                return RC_MISSING

            # ---- 2) --reset：先查引用，再删 ----
            deleted = 0
            detached = 0
            if reset:
                report = reference_report(conn)
                print_reference_report(report)
                refs = int(report["favorites"]) + int(report["appointments"])
                if refs and not force:
                    print("")
                    print(f"[!!] 拒绝删除：{refs} 行仍引用现有微展位"
                          f"（favorites={report['favorites']}, "
                          f"appointments={report['appointments']}）。")
                    print("[XX] --reset 未执行，库未改动。"
                          "确认要连带删除请显式追加 --force"
                          "（引用行不会被本脚本删除，需人工处理）。")
                    if apply:
                        conn.execute("ROLLBACK")
                    return RC_REFUSED
                if refs:
                    print(f"[!!] --force：忽略 {refs} 行引用，继续删除"
                          f"（favorites/appointments 行本脚本不删，会变成孤儿引用）。")

                if apply:
                    # 先断开平台展品的挂载（保留展品本身，只清 micro_booth_id）
                    detached = conn.execute(
                        'UPDATE "products" SET micro_booth_id = NULL '
                        "WHERE micro_booth_id IS NOT NULL"
                    ).rowcount
                    # 删除全部微展位（status 不限）
                    deleted = conn.execute(f'DELETE FROM "{TABLE}"').rowcount
                    print(f"[OK] --reset：删除 {TABLE} {deleted} 行；"
                          f"products.micro_booth_id 置空 {detached} 行")
                else:
                    print(f"[--] --reset：将删除 {TABLE} {booths_before} 行"
                          f"（status 不限），并将 products.micro_booth_id 置空"
                          f"（dry-run 不执行）")
                    deleted = booths_before

            # ---- 3) 取名录展商 → 组装 payload ----
            rows = fetch_catalog_rows(conn, limit)
            payload, skipped = build_payload(rows)
            print(f"[--] 名录展商取前 {limit}（product_count DESC, id ASC）："
                  f"实际 {len(rows)} 行，可写入 {len(payload)} 行"
                  f"{f'，跳过空名 {skipped} 行' if skipped else ''}")

            # ---- 4) 幂等 upsert：catalog_exhibitor_id 为唯一键 ----
            existing = existing_booth_map(conn, [p["catalog_exhibitor_id"] for p in payload])
            inserts = [p for p in payload if p["catalog_exhibitor_id"] not in existing]
            updates = [p for p in payload if p["catalog_exhibitor_id"] in existing]
            print(f"[--] 待处理：插入 {len(inserts)} 行 / 更新 {len(updates)} 行"
                  f"（已存在 {len(existing)} 条同名录展商的微展位）")

            booth_ids: Dict[int, Optional[int]] = {
                p["catalog_exhibitor_id"]: existing.get(p["catalog_exhibitor_id"])
                for p in payload
            }

            if apply:
                if account_id is None:  # 只有 created 分支会给 id；防御性断言
                    print("[XX] 内部错误：applied 模式下名录归属账号 id 为空")
                    conn.execute("ROLLBACK")
                    return RC_MISSING

                for p in inserts:
                    cur = conn.execute(
                        f'INSERT INTO "{TABLE}" ('
                        "exhibitor_id, exhibition_id, catalog_exhibitor_id, name, "
                        "description, logo_url, industry_domain, membership_tier, "
                        "view_count, search_appearances, favorite_count, status) "
                        "VALUES (?, ?, ?, ?, ?, NULL, ?, 'free', 0, 0, 0, 'active')",
                        (
                            account_id,
                            p["exhibition_id"],
                            p["catalog_exhibitor_id"],
                            p["name"],
                            p["description"],
                            p["industry_domain"],
                        ),
                    )
                    booth_ids[p["catalog_exhibitor_id"]] = int(cur.lastrowid)

                for p in updates:
                    conn.execute(
                        f'UPDATE "{TABLE}" SET name = ?, description = ?, '
                        "industry_domain = ?, updated_at = CURRENT_TIMESTAMP "
                        "WHERE id = ?",
                        (
                            p["name"],
                            p["description"],
                            p["industry_domain"],
                            existing[p["catalog_exhibitor_id"]],
                        ),
                    )

                conn.execute("COMMIT")
                print(f"[OK] 写入完成：插入 {len(inserts)} 行 / 更新 {len(updates)} 行")
            else:
                for p in inserts:
                    booth_ids[p["catalog_exhibitor_id"]] = None  # 待插入，无 id

            # ---- 5) 核对 + 抽样 ----
            booths_after = _count(conn, TABLE)
            print("")
            print("[==] 汇总")
            print(f"     模式：{'APPLY' if apply else 'DRY-RUN（未写库）'}")
            print(f"     名录归属账号：id={account_id if account_id is not None else '(dry-run 待创建)'}"
                  f" username={ACCOUNT_USERNAME} role=exhibitor（状态：{account_state}）")
            print(f"     --reset 删除行数：{deleted}" if reset else "     --reset：未指定（未删除任何行）")
            if reset and apply:
                print(f"     products.micro_booth_id 置空行数：{detached}")
            print(f"     插入行数：{len(inserts)}")
            print(f"     更新行数：{len(updates)}")
            print(f"     {TABLE} 行数：{booths_before} -> {booths_after}"
                  f"{'（dry-run 未变）' if not apply else ''}")
            print(f"     统计合计（必须全 0，无编造数字）：view_count={_sum(conn, 'view_count')} "
                  f"favorite_count={_sum(conn, 'favorite_count')} "
                  f"search_appearances={_sum(conn, 'search_appearances')}")

            print("")
            print("[==] 抽样 5 条（id / name / industry_domain / product_count）")
            for p in payload[:5]:
                booth_id = booth_ids.get(p["catalog_exhibitor_id"])
                shown_id = booth_id if booth_id is not None else "(待插入)"
                industry = p["industry_domain"] or "-"
                print(f"     id={shown_id}  {p['name']}  |  {industry}  |  "
                      f"product_count={p['product_count']}")

            if apply:
                orphans = conn.execute(
                    'SELECT COUNT(*) FROM "micro_booths" '
                    "WHERE catalog_exhibitor_id IS NOT NULL "
                    "AND catalog_exhibitor_id NOT IN (SELECT id FROM catalog_exhibitors)"
                ).fetchone()[0]
                fk_errors = conn.execute(f'PRAGMA foreign_key_check("{TABLE}")').fetchall()
                print("")
                print(f"[--] 外键自检：catalog_exhibitor_id 悬空 {orphans} 行；"
                      f"PRAGMA foreign_key_check({TABLE}) 报错 {len(fk_errors)} 行")
                if orphans or fk_errors:
                    print("[XX] 存在悬空外键，请检查！")
                    return RC_SCHEMA
            else:
                print("")
                print("[--] DRY-RUN 结束，未改动数据库。加 --apply 才会真正写入。")
            return RC_OK
        except Exception:
            if apply:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
            raise
    finally:
        conn.close()


def main(argv: List[str] | None = None) -> int:
    harden_stdout()
    parser = argparse.ArgumentParser(
        description="用真实展商名录（catalog_exhibitors）填充 micro_booths；默认 dry-run"
    )
    parser.add_argument(
        "--db", default=default_db_path(),
        help="SQLite 数据库路径（默认：<expohub-backend>/expohub.db，可用 EXPOHUB_DB 覆盖）",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"取 product_count 最高的前 N 家名录展商（默认 {DEFAULT_LIMIT}）",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true",
        help="真正写库（默认 dry-run，只打印）",
    )
    mode.add_argument(
        "--dry-run", action="store_true",
        help="显式 dry-run（与默认行为相同：只打印，不写库）",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="删除现有 micro_booths 全部行（默认不删；有 favorites/appointments 引用时拒绝，除非 --force）",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="即使 favorites/appointments 引用了微展位也允许 --reset 删除",
    )
    args = parser.parse_args(argv)
    return run(args.db, args.limit, args.apply, args.reset, args.force)


if __name__ == "__main__":
    sys.exit(main())
