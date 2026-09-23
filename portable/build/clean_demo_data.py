#!/usr/bin/env python3
"""把开发库复制一份并清理演示数据，供便携试用包使用。

**只写目标副本，绝不碰源库** —— 源库是开发用的，删数据不可逆。

清理内容：
  1. 指定的测试账号（默认 222 / 333 / user）及其**级联依赖**
  2. 指定的垃圾展会（默认 id=6，标题「请问」、日期 0123 年）
  3. 顺带扫掉"孤儿行"——外键指向已不存在父行的记录，页面上本来也渲染不出来

孤儿扫描是通用的：删完目标记录后反复迭代，直到没有新的孤儿产生。
比手工列级联表可靠得多（手工列必然漏，实测漏过两次）。

用法：
    python clean_demo_data.py <源库> <目标库>
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys

# 需要清掉的测试账号（按用户名匹配，比按 id 稳）
JUNK_USERNAMES = ("222", "333", "user")
# 需要清掉的垃圾展会（按 id）
JUNK_EXHIBITION_IDS = (6,)
# 年份荒谬的展会也一并清掉（测试时手滑输的日期，如 0123 年）
SANITY_YEAR_MIN, SANITY_YEAR_MAX = 2000, 2100


def main(src: str, dst: str) -> int:
    if not os.path.isfile(src):
        print(f"[错误] 源库不存在: {src}")
        return 2
    if os.path.abspath(src) == os.path.abspath(dst):
        print("[错误] 源库与目标库是同一个文件，拒绝执行（会破坏开发数据）")
        return 2

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"[1] 已复制 {src}\n         -> {dst}")
    print("    （源库未被修改）\n")

    con = sqlite3.connect(dst)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    def scalar(sql, args=()):
        cur.execute(sql, args)
        return cur.fetchone()[0]

    # ---- 收集所有外键关系，供孤儿扫描使用 ----
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]
    fks = []
    for t in tables:
        cur.execute(f"PRAGMA foreign_key_list('{t}')")
        for fk in cur.fetchall():
            if fk[2] in tables:
                fks.append((t, fk[3], fk[2], fk[4]))   # child, child_col, parent, parent_col

    def orphans() -> dict:
        out = {}
        for ct, cc, pt, pc in fks:
            cur.execute(
                f'SELECT COUNT(*) FROM "{ct}" '
                f'WHERE "{cc}" IS NOT NULL AND "{cc}" NOT IN (SELECT "{pc}" FROM "{pt}")'
            )
            n = cur.fetchone()[0]
            if n:
                out[f"{ct}.{cc} -> {pt}"] = n
        return out

    before = {
        "exhibitions": scalar("SELECT COUNT(*) FROM exhibitions"),
        "users": scalar("SELECT COUNT(*) FROM users"),
    }
    pre_orphans = orphans()
    print(f"[2] 清理前: exhibitions={before['exhibitions']}  users={before['users']}")
    if pre_orphans:
        print(f"    另发现历史遗留孤儿行 {sum(pre_orphans.values())} 条（本来也渲染不出来）")

    # ---- 定位要删的记录 ----
    q = ",".join("?" * len(JUNK_USERNAMES))
    cur.execute(f"SELECT id, username FROM users WHERE username IN ({q})", JUNK_USERNAMES)
    junk_users = cur.fetchall()
    junk_uids = [r[0] for r in junk_users]

    q = ",".join("?" * len(JUNK_EXHIBITION_IDS))
    cur.execute(f"SELECT id, title FROM exhibitions WHERE id IN ({q})", JUNK_EXHIBITION_IDS)
    junk_exhs = cur.fetchall()

    cur.execute("SELECT id, title, start_date FROM exhibitions")
    for eid, title, start in cur.fetchall():
        if start and str(start)[:4].isdigit():
            y = int(str(start)[:4])
            if not (SANITY_YEAR_MIN <= y <= SANITY_YEAR_MAX):
                junk_exhs.append((eid, f"{title} [日期异常 {start}]"))

    # ---- 删除（先关外键约束，靠随后的孤儿扫描兜底）----
    cur.execute("PRAGMA foreign_keys=OFF")
    print("\n[3] 删除目标记录")
    if junk_uids:
        qq = ",".join("?" * len(junk_uids))
        cur.execute(f"DELETE FROM users WHERE id IN ({qq})", junk_uids)
        print(f"    users: {cur.rowcount} 行  ({', '.join(r[1] for r in junk_users)})")
    else:
        print("    未匹配到测试账号（可能已清理过）")
    for eid, title in dict(junk_exhs).items():
        cur.execute("DELETE FROM exhibitions WHERE id=?", (eid,))
        print(f"    exhibitions: {cur.rowcount} 行  (id={eid} 「{title}」)")

    print("\n[4] 孤儿扫描（迭代到不再产生新孤儿）")
    removed: dict[str, int] = {}
    rnd = 0
    while True:
        rnd += 1
        n_this = 0
        for ct, cc, pt, pc in fks:
            cur.execute(
                f'DELETE FROM "{ct}" '
                f'WHERE "{cc}" IS NOT NULL AND "{cc}" NOT IN (SELECT "{pc}" FROM "{pt}")'
            )
            if cur.rowcount > 0:
                removed[f"{ct}.{cc}"] = removed.get(f"{ct}.{cc}", 0) + cur.rowcount
                n_this += cur.rowcount
        if n_this == 0:
            break
        print(f"    第 {rnd} 轮: 删除 {n_this} 行")
    for k, v in sorted(removed.items(), key=lambda x: -x[1]):
        print(f"      {k}: {v} 行")

    con.commit()
    cur.execute("PRAGMA foreign_keys=ON")

    # ---- 校验 ----
    print("\n[5] 校验")
    integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
    viol = cur.execute("PRAGMA foreign_key_check").fetchall()
    left = orphans()
    print(f"    完整性: {integrity}")
    print(f"    外键校验: {'0 违规' if not viol else f'{len(viol)} 处违规!'}")
    print(f"    残留孤儿: {sum(left.values()) if left else 0}")
    print(f"    exhibitions={scalar('SELECT COUNT(*) FROM exhibitions')}  "
          f"users={scalar('SELECT COUNT(*) FROM users')}  "
          f"products={scalar('SELECT COUNT(*) FROM products')}  "
          f"micro_booths={scalar('SELECT COUNT(*) FROM micro_booths')}")

    con.close()
    ok = integrity == "ok" and not viol and not left
    print("\n" + ("演示数据清理完成 ✅" if ok else "清理后仍有问题 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
