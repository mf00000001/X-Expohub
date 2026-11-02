#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按**显式 ID**清理测试展会（默认 dry-run，不写库）。

⚠️ 为什么只按显式 ID：
    STATE.md 记载过教训——曾用「日期年份不在 2000-2100 就当垃圾删」的启发式自动
    判断，**误删过一条真实展会**（id=6「请问」）。因此本脚本**不做任何自动识别**：
    清哪些展会由人在下面 `JUNK_EXHIBITION_IDS` 里显式列出，一个不写就一个不动。

删除行为与接口 `DELETE /api/exhibitions/{id}`（expohub-backend/app/modules/expo/exhibitions.py）
保持一致：
    · booths / ticketing_orders / ticket_types / reviews / appointments / registrations —— 随展删除
    · products（含 booth_id 解绑）/ procurements —— 只解绑 exhibition_id，保留展商/采购商资产
    · 若该展存在已支付票务订单 —— 拒绝删除（需先处理退款与订单归档）

安全措施：
    · 默认 dry-run，**必须显式 `--apply` 才会写库**；
    · `--apply` 前先在同目录备份为 `<库名>.bak-YYYYmmdd-HHMMSS`；
    · 整个删除在一个事务里完成，失败回滚；
    · 删除后跑 `PRAGMA integrity_check` 与 `PRAGMA foreign_key_check` 自检。

用法：
    # 1) 看会删什么（默认就是 dry-run，只读打开库）
    python scripts/clean_test_exhibitions.py
    python scripts/clean_test_exhibitions.py --dry-run

    # 2) 真的删（先备份再删）
    python scripts/clean_test_exhibitions.py --apply

    # 3) 指定库文件（相对路径按当前工作目录解析）
    python scripts/clean_test_exhibitions.py --db expohub-backend/expohub.db

退出码：0 = 正常；1 = 拒绝执行/校验失败；2 = 参数或库文件有问题。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

# ============================================================
# 配置
# ============================================================

# 要清理的展会 id —— **必须人来显式列**，禁止改成任何自动判断。
# 当前两条是历史脏数据（start_date='0123-12-03'，年份 123，且为 published 会出现在公开列表）。
JUNK_EXHIBITION_IDS = [6, 7]

# 随展删除的表，顺序与接口实现完全一致（先清订单/票种，再清评价/预约/报名，最后清展位）
CASCADE_DELETE_TABLES = [
    "ticketing_orders",
    "ticket_types",
    "reviews",
    "appointments",
    "registrations",
    "booths",
]

# 只解绑（置 NULL）、不删数据的表 -> 需要置空的列（与接口一致）
UNBIND_TABLES = {
    "products": ("exhibition_id", "booth_id"),
    "procurements": ("exhibition_id",),
}

# 有 exhibition_id 列但没有建外键的表：只统计、不处理（接口也不处理），
# 用于让人确认删完不会留下"看不见的悬挂行"。
INFO_ONLY_TABLES = ["micro_booths", "tickets", "onsite_checkin_logs"]

# 涉及的所有表（用于"删除前后计数"）
ALL_AFFECTED_TABLES = ["exhibitions"] + CASCADE_DELETE_TABLES + list(UNBIND_TABLES) + INFO_ONLY_TABLES

# 默认库路径：仓库根目录下 expohub-backend/expohub.db（与脚本所在位置无关，避免 cwd 影响）
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(REPO_ROOT, "expohub-backend", "expohub.db")


# ============================================================
# 工具函数
# ============================================================

def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _count(cur: sqlite3.Cursor, table: str) -> int:
    if not _table_exists(cur, table):
        return -1  # -1 表示该表不存在
    return cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _count_refs(cur: sqlite3.Cursor, table: str, exhibition_id: int) -> int:
    """统计某表里引用该展会的行数（表不存在返回 -1）。"""
    if not _table_exists(cur, table):
        return -1
    return cur.execute(
        f"SELECT COUNT(*) FROM {table} WHERE exhibition_id=?", (exhibition_id,)
    ).fetchone()[0]


def _snapshot_counts(cur: sqlite3.Cursor) -> dict:
    """当前各表总行数快照，用于打印"删除前后计数"。"""
    return {t: _count(cur, t) for t in ALL_AFFECTED_TABLES}


def _find_junk(cur: sqlite3.Cursor) -> list:
    """按显式 ID 取目标展会（不附加任何其他筛选条件）。"""
    placeholders = ",".join("?" for _ in JUNK_EXHIBITION_IDS)
    rows = cur.execute(
        f"SELECT id, title, start_date, end_date, status FROM exhibitions "
        f"WHERE id IN ({placeholders}) ORDER BY id",
        list(JUNK_EXHIBITION_IDS),
    ).fetchall()
    return rows


def _paid_order_counts(cur: sqlite3.Cursor) -> dict:
    """统计目标展会上的已支付订单（接口遇到这类展会会拒绝删除，脚本同样拒绝）。"""
    if not _table_exists(cur, "ticketing_orders"):
        return {}
    placeholders = ",".join("?" for _ in JUNK_EXHIBITION_IDS)
    rows = cur.execute(
        f"SELECT exhibition_id, COUNT(*) FROM ticketing_orders "
        f"WHERE status='paid' AND exhibition_id IN ({placeholders}) GROUP BY exhibition_id",
        list(JUNK_EXHIBITION_IDS),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def _print_plan(cur: sqlite3.Cursor, targets: list) -> None:
    """打印每个目标展会会被如何处理（dry-run 与 apply 共用的"计划"部分）。"""
    print("=" * 68)
    print(f"目标展会（显式 ID：{JUNK_EXHIBITION_IDS}）")
    print("=" * 68)
    if not targets:
        print("    ⚠️ 库里没找到这些 ID 的展会（可能已被删除？）")
        print()
        return

    for eid, title, start_date, end_date, status in targets:
        print(f"  id={eid}  title=「{title}」")
        print(f"         start_date={start_date}   end_date={end_date}   status={status}")
        print("         随展删除：", end="")
        parts = []
        for table in CASCADE_DELETE_TABLES:
            n = _count_refs(cur, table, eid)
            parts.append(f"{table}={'无此表' if n < 0 else n}")
        print(", ".join(parts))
        print("         只解绑：  ", end="")
        parts = []
        for table in UNBIND_TABLES:
            n = _count_refs(cur, table, eid)
            parts.append(f"{table}={'无此表' if n < 0 else n}")
        print(", ".join(parts))
        print("         （仅统计）", end="")
        parts = []
        for table in INFO_ONLY_TABLES:
            n = _count_refs(cur, table, eid)
            parts.append(f"{table}={'无此表' if n < 0 else n}")
        print(", ".join(parts))
        print()


def _delete_one(cur: sqlite3.Cursor, exhibition_id: int) -> None:
    """按接口顺序删除单个展会及其级联数据。调用前须置 PRAGMA foreign_keys=ON。"""
    # 1) 随展删除（顺序与 exhibitions.py 的 delete 端点一致）
    for table in ("ticketing_orders", "ticket_types", "reviews",
                  "appointments", "registrations"):
        if _table_exists(cur, table):
            cur.execute(f"DELETE FROM {table} WHERE exhibition_id=?", (exhibition_id,))
            if cur.rowcount > 0:
                print(f"      [删] {table:<18} {cur.rowcount} 行")

    # 2) 只解绑展品（含归属已删展位的展品）与采购需求
    if _table_exists(cur, "products"):
        cur.execute(
            "UPDATE products SET exhibition_id=NULL, booth_id=NULL WHERE exhibition_id=?",
            (exhibition_id,),
        )
        if cur.rowcount > 0:
            print(f"      [解绑] products           {cur.rowcount} 行（保留展商资产）")
        # 补充：展位属于本展、但 exhibition_id 指向别处的展品，只解 booth_id，
        # 否则删 booths 时会撞 products.booth_id 外键（接口注释里的"含归属已删展位的展品"即此意）
        cur.execute(
            "UPDATE products SET booth_id=NULL "
            "WHERE booth_id IN (SELECT id FROM booths WHERE exhibition_id=?)",
            (exhibition_id,),
        )
        if cur.rowcount > 0:
            print(f"      [解绑] products.booth_id   {cur.rowcount} 行（跨展归属展位）")
    if _table_exists(cur, "procurements"):
        cur.execute("UPDATE procurements SET exhibition_id=NULL WHERE exhibition_id=?", (exhibition_id,))
        if cur.rowcount > 0:
            print(f"      [解绑] procurements       {cur.rowcount} 行（保留采购商资产）")

    # 3) 最后删展位
    if _table_exists(cur, "booths"):
        cur.execute("DELETE FROM booths WHERE exhibition_id=?", (exhibition_id,))
        if cur.rowcount > 0:
            print(f"      [删] booths               {cur.rowcount} 行")

    # 4) 删展会本体
    cur.execute("DELETE FROM exhibitions WHERE id=?", (exhibition_id,))
    print(f"      [删] exhibitions          {cur.rowcount} 行  (id={exhibition_id})")


# ============================================================
# dry-run / apply
# ============================================================

def run_dry_run(db_path: str) -> int:
    """只读打开库，列出"如果 --apply 会删什么"，绝不写库。"""
    print(f"[dry-run] 只读打开：{db_path}")
    print("           （默认就是 dry-run；真要删请显式加 --apply）")
    print()
    # mode=ro：由 SQLite 保证不可能写库
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        before = _snapshot_counts(cur)
        targets = _find_junk(cur)

        _print_plan(cur, targets)

        paid = _paid_order_counts(cur)
        if paid:
            print("⛔ 这些展会上存在已支付票务订单，接口同样会拒绝删除：")
            for eid, n in sorted(paid.items()):
                print(f"      id={eid}: {n} 笔已支付订单")
            print()

        print(f"将删除的展会：{[t[0] for t in targets]}  "
              f"（共 {len(targets)} 场；exhibitions {before['exhibitions']} → "
              f"{before['exhibitions'] - len(targets)}）")
        print()
        print("本次 dry-run 未写库：连接以 mode=ro 打开，任何写入都会被 SQLite 拒绝。")
        return 0
    finally:
        con.close()


def run_apply(db_path: str) -> int:
    """备份 -> 事务内删除 -> 自检 -> 打印前后计数。"""
    # 0) 先只读探一下：库结构对不对、有没有目标行（没有就不必留一份无用备份）
    probe = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        if not _table_exists(probe.cursor(), "exhibitions"):
            print(f"[错误] 该库里没有 exhibitions 表：{db_path}")
            return 2
        if not _find_junk(probe.cursor()):
            print(f"库里没有这些 ID 的展会（{JUNK_EXHIBITION_IDS}），无需删除；未生成备份")
            return 0
    finally:
        probe.close()

    # 1) 备份（同目录 .bak-时间戳）
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{db_path}.bak-{stamp}"
    shutil.copy2(db_path, backup_path)
    print(f"[1] 已备份：{backup_path}")
    print()

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON")  # 与接口（ORM）一致：级联顺序错了就报错，不许留孤儿
    try:
        cur = con.cursor()
        before = _snapshot_counts(cur)
        targets = _find_junk(cur)
        if not targets:
            print("[2] 库里没有这些 ID 的展会，无需删除（备份已生成，可直接删掉）")
            return 0
        _print_plan(cur, targets)

        # 2) 已支付订单 -> 拒绝（与接口一致）
        paid = _paid_order_counts(cur)
        if paid:
            print("⛔ 拒绝执行：目标展会上存在已支付票务订单（接口同样会拒绝删除）")
            for eid, n in sorted(paid.items()):
                print(f"      id={eid}: {n} 笔已支付订单")
            print("   请先处理退款与订单归档；本次未改动数据库。")
            print(f"   备份已生成（未使用）：{backup_path}")
            return 1

        # 3) 事务内删除（异常自动回滚）
        print("[2] 开始删除（单事务，失败自动回滚）")
        try:
            for eid, title, *_ in targets:
                print(f"    -> 展会 id={eid}「{title}」")
                _delete_one(cur, eid)
            con.commit()
        except Exception as exc:                      # noqa: BLE001 —— 任何异常都要回滚并报出来
            con.rollback()
            print(f"❌ 删除失败，已回滚：{exc!r}")
            print(f"   库文件未被改动；备份仍保留在 {backup_path}")
            return 1
        print("    已提交\n")

        # 4) 前后计数
        after = _snapshot_counts(cur)
        print("[3] 删除前后计数")
        print(f"    {'表名':<22} {'前':>7} {'后':>7} {'变化':>7}")
        for table in ALL_AFFECTED_TABLES:
            b, a = before.get(table, -1), after.get(table, -1)
            if b < 0 or a < 0:
                print(f"    {table:<22} {'(表不存在)':>7}")
                continue
            print(f"    {table:<22} {b:>7} {a:>7} {a - b:>+7}")
        print()

        # 5) 自检
        integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
        viol = cur.execute("PRAGMA foreign_key_check").fetchall()
        print("[4] 自检")
        print(f"    integrity_check   : {integrity}")
        print(f"    foreign_key_check : {'0 违规' if not viol else f'{len(viol)} 处违规 ⛔'}")
        done = _find_junk(cur)
        print(f"    目标展会残留      : {len(done)} 场")
        print()
        ok = integrity == "ok" and not viol and not done
        print(f"完成 ✅（备份：{backup_path}）" if ok else "完成但自检未通过 ❌")
        return 0 if ok else 1
    finally:
        con.close()


# ============================================================
# 入口
# ============================================================

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="按显式 ID 清理测试展会（默认 dry-run）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="真的执行删除（会先备份库为 .bak-时间戳）；不加就是 dry-run",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只列计划、不写库（默认行为，写出来是为了显式表达）",
    )
    parser.add_argument(
        "--db", default=DEFAULT_DB,
        help=f"SQLite 库路径，默认 {DEFAULT_DB}",
    )
    args = parser.parse_args(argv)

    if args.apply and args.dry_run:
        print("[错误] --apply 与 --dry-run 互斥")
        return 2

    db_path = os.path.abspath(os.path.expanduser(args.db))
    if not os.path.isfile(db_path):
        print(f"[错误] 库文件不存在：{db_path}")
        return 2

    print("=" * 68)
    print("按显式 ID 清理测试展会（不做任何自动判断 —— 见 STATE.md 教训）")
    print(f"目标 ID：{JUNK_EXHIBITION_IDS}")
    print("=" * 68)
    print()

    return run_apply(db_path) if args.apply else run_dry_run(db_path)


if __name__ == "__main__":
    sys.exit(main())
