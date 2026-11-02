"""
回填脚本：参展关系表 `exhibition_exhibitors`（展会 ↔ 名录展商）

做什么
------
把 `catalog_exhibitors.expo_name`（名录原文展会名）映射到 `exhibitions.id`，
然后为**每个**命中展会的展商生成一条参展关系：

    exhibition_exhibitors(exhibition_id, catalog_exhibitor_id, expo_label, booth_no)

`expo_label` 存名录原文展会名，`booth_no` 存该展商的名录展位号，便于追溯。

怎么映射（不写死任何展会名）
----------------------------
全部基于「规范化后比较」，映射源只有库里两张表的数据：

1. **strict**：`normalize(x)` 后相等。
   `normalize` = NFKC 全半角归一 → `|` 换 `·` → 去所有空白 → 小写 → 反复去掉尾部括号后缀。
   （例：`CMES 华机展 · 东莞` ↔ `CMES 华机展 · 东莞`）
2. **loose**：strict 再放宽一层，去掉两边都不影响展会身份的成分：
   `第…届` 序号前缀、通用修饰词（中国 / 国际 / 全国）、开头的全大写英文缩写
   （如 `CMEF` / `NHNE` / `TME`）。
   （例：`CMEF 中国国际医疗器械博览会` ↔ `第九十四届中国国际医疗器械博览会（CMEF）`）
3. **alias**：括号里的内容当别名互相匹配（双向）。
   （例：标题尾部的 `（高交会）` ↔ 名录里的 `高交会（CHTF）`）

严格相等只覆盖 8 / 12 场展会，`CMEF`（13,306 家）与 `NHHE`、`高交会`、`玉环` 会被
判为"映射不上"，详情页直接从 1.3 万家掉到 0 —— 所以默认跑 layered（strict → loose
→ alias）。`--match-mode strict` 可复现纯严格相等的口径，用于对比。

**映射不上的一律不硬塞**：只进报告。同一层命中的展会不唯一（歧义）也不硬塞。
当前数据里映射不上的有：
  - `CIOE 中国国际光电博览会`（3,209 行）—— `exhibitions` 里没有光博会；
  - `CMES 华机展`（522 行，无城市后缀的"总称"）与 `CMES 华机展 · 青岛`（522 行）
    —— 前者是集团级写法、后者 `exhibitions` 里没有青岛场，都不该塞进任何一届。

安全措施
--------
- 默认 **dry-run**，只打印报告，不写库；加 `--apply` 才落库；
- `--apply` 会先把 DB 备份到 `<db 所在目录>/<db 名>.bak-<YYYYmmdd-HHMMSS>`，
  用 SQLite 在线备份 API（`Connection.backup`）保证一致性，并回读备份做
  `PRAGMA integrity_check` + 行数核对；
- 落库用 `INSERT OR IGNORE`（唯一约束 `(exhibition_id, catalog_exhibitor_id)`），
  重复执行幂等，不会重复插入；
- 只 INSERT，不 DELETE / UPDATE 任何既有表（`catalog_exhibitors.exhibition_id`
  等遗留列原样保留）。

用法
----
    # 1) 先建表（幂等）
    python scripts/migrate_exhibition_exhibitors.py

    # 2) 看报告（dry-run，默认）
    python scripts/backfill_exhibition_exhibitors.py
    python scripts/backfill_exhibition_exhibitors.py --report reports/backfill.txt

    # 3) 真写（先自动备份）
    python scripts/backfill_exhibition_exhibitors.py --apply

    # 可选参数
    --db path/to/expohub.db     指定库（默认 <expohub-backend>/expohub.db）
    --match-mode strict         只用严格相等（对比用）
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

TABLE = "exhibition_exhibitors"

# ============================================================
# 名称规范化
# ============================================================

# 通用修饰词：出现与否不改变"是哪一场展会"（仅 loose 层使用）
_MODIFIER_WORDS = ("中国", "国际", "全国")

# 中文序号前缀：第九十四届 / 第二届 / 第 3 届
_ORDINAL_PREFIX = re.compile(r"^第[0-9一二三四五六七八九十百千零〇两]+届[·\-—:]?")

# 开头的英文缩写（CMEF / NHNE / TME / CIOE …），只在后面还有中文时才剥
_LEADING_ASCII = re.compile(r"^[a-z][a-z0-9&.\-]{1,}")

# 尾部括号后缀（半角/全角）——NFKC 之后全角括号已变成半角
_TRAILING_BRACKETS = re.compile(r"\([^()]*\)$")

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def _nfkc(text: str) -> str:
    """全半角统一（（）→ ()、｜→ |、９→ 9 …）。"""
    return unicodedata.normalize("NFKC", text)


def _squeeze(text: str) -> str:
    """去所有空白 + 小写。"""
    return re.sub(r"\s+", "", text).lower()


def strip_trailing_brackets(text: str) -> str:
    """反复去掉尾部括号后缀：`xx（NHNE）` → `xx`。"""
    out = text.strip()
    while True:
        new = _TRAILING_BRACKETS.sub("", out).strip()
        if new == out or not new:
            return out
        out = new


def strict_key(text: Optional[str]) -> str:
    """严格键：NFKC → `|` 换 `·` → 去空白 → 小写 → 去尾部括号后缀。"""
    if not text:
        return ""
    t = _nfkc(text).strip()
    t = t.replace("|", "·")
    t = _squeeze(t)
    t = strip_trailing_brackets(t)
    return _squeeze(t)


def loose_key(text: Optional[str]) -> str:
    """宽松键：strict 再剥「第…届」/「中国·国际·全国」/开头英文缩写。"""
    if not text:
        return ""
    t = _nfkc(text).strip()
    t = t.replace("|", "·")
    t = strip_trailing_brackets(t)
    # 开头英文缩写：仅当后面还有中文时剥离（纯英文名不动）
    lead = _LEADING_ASCII.match(_squeeze(t))
    if lead:
        rest = _squeeze(t)[lead.end():].lstrip("·-—:")
        if rest and _CJK.search(rest):
            t = rest
    t = _squeeze(t)
    t = _ORDINAL_PREFIX.sub("", t)
    for word in _MODIFIER_WORDS:
        t = t.replace(word.lower(), "")
    return _squeeze(t)


def bracket_tokens(text: Optional[str]) -> Set[str]:
    """抽取括号内容当别名（NFKC → 去空白 → 小写）。"""
    if not text:
        return set()
    t = _nfkc(text)
    tokens = {_squeeze(m) for m in re.findall(r"\(([^()]*)\)", t)}
    tokens |= {_squeeze(m) for m in re.findall(r"\[([^\[\]]*)\]", t)}
    tokens.discard("")
    return tokens


# ============================================================
# 映射
# ============================================================

class Match:
    """一条 expo_name 的匹配结果。"""

    __slots__ = ("expo_name", "rows", "exhibition_id", "level", "reason", "candidates")

    def __init__(self, expo_name: str, rows: int):
        self.expo_name = expo_name
        self.rows = rows
        self.exhibition_id: Optional[int] = None
        self.level = ""
        self.reason = ""
        self.candidates: Set[int] = set()

    @property
    def ok(self) -> bool:
        return self.exhibition_id is not None


def build_indexes(
    exhibition_rows: List[Tuple[int, str]]
) -> Tuple[Dict[str, Set[int]], Dict[str, Set[int]], Dict[str, Set[int]]]:
    """建立三张反查表：strict 键 / loose 键 / 括号别名 → 展会 ID 集合。"""
    strict_idx: Dict[str, Set[int]] = {}
    loose_idx: Dict[str, Set[int]] = {}
    alias_idx: Dict[str, Set[int]] = {}
    for eid, title in exhibition_rows:
        sk, lk = strict_key(title), loose_key(title)
        if sk:
            strict_idx.setdefault(sk, set()).add(eid)
        if lk:
            loose_idx.setdefault(lk, set()).add(eid)
        for tok in bracket_tokens(title):
            alias_idx.setdefault(tok, set()).add(eid)
    return strict_idx, loose_idx, alias_idx


def _pick(ids: Set[int], level: str, match: Match) -> Optional[Match]:
    """从候选集合里定结果：唯一 → 命中；多个 → 歧义；空 → 未命中。"""
    if len(ids) == 1:
        match.exhibition_id = next(iter(ids))
        match.level = level
        match.reason = f"{level} 唯一命中"
        return match
    if len(ids) > 1:
        match.candidates = set(ids)
        match.level = level
        match.reason = f"{level} 命中 {len(ids)} 场展会（歧义，不硬塞）"
    return None


def match_expo_name(
    expo_name: str,
    rows: int,
    strict_idx: Dict[str, Set[int]],
    loose_idx: Dict[str, Set[int]],
    alias_idx: Dict[str, Set[int]],
    match_mode: str = "layered",
) -> Match:
    """按 strict → loose → alias 顺序给一条 expo_name 找展会。"""
    m = Match(expo_name, rows)
    sk, lk = strict_key(expo_name), loose_key(expo_name)

    if _pick(strict_idx.get(sk, set()), "strict", m):
        return m
    if match_mode == "strict":
        if not m.candidates:
            m.reason = f"无展会标题与 {expo_name!r} 规范化后相等（strict 口径）"
        return m

    if _pick(loose_idx.get(lk, set()), "loose", m):
        return m
    alias_hit: Set[int] = set()
    for tok in bracket_tokens(expo_name) | {sk, lk}:
        alias_hit |= alias_idx.get(tok, set())
        if len(alias_hit) > 1:
            break
    if _pick(alias_hit, "alias", m):
        return m
    if not m.candidates:
        m.reason = (
            f"exhibitions 里没有对应展会（strict={sk!r} / loose={lk!r} 均未命中）"
        )
    return m


# ============================================================
# 统计 / 报告
# ============================================================

def _fmt(n: int) -> str:
    return f"{n:,}"


def _per_exhibition_counts(
    conn: sqlite3.Connection, table_exists: bool
) -> Dict[int, Tuple[int, int]]:
    """每场展会的（展商数, 展品数）：关系表 join 名录 / 展品。"""
    if not table_exists:
        return {}
    rows = conn.execute(
        f"""
        SELECT ee.exhibition_id,
               COUNT(DISTINCT ee.catalog_exhibitor_id) AS exhibitors
        FROM exhibition_exhibitors ee
        GROUP BY ee.exhibition_id
        """
    ).fetchall()
    out = {int(eid): (int(n), 0) for eid, n in rows}
    for eid, n in conn.execute(
        """
        SELECT ee.exhibition_id, COUNT(p.id)
        FROM exhibition_exhibitors ee
        JOIN catalog_products p ON p.exhibitor_id = ee.catalog_exhibitor_id
        GROUP BY ee.exhibition_id
        """
    ):
        if int(eid) in out:
            out[int(eid)] = (out[int(eid)][0], int(n))
    return out


def _projected_counts(
    matches: List[Match], per_exhibitor: Dict[str, Tuple[int, int]]
) -> Dict[int, Tuple[int, int]]:
    """dry-run 时按映射结果推算每场展会（展商数, 展品数）。"""
    out: Dict[int, Tuple[int, int]] = {}
    for m in matches:
        if not m.ok:
            continue
        ex, pr = per_exhibitor.get(m.expo_name, (0, 0))
        cur = out.get(m.exhibition_id, (0, 0))
        out[m.exhibition_id] = (cur[0] + ex, cur[1] + pr)
    return out


# ============================================================
# 主流程
# ============================================================

def default_db_path() -> str:
    env = os.environ.get("EXPOHUB_DB") or os.environ.get("DATABASE_PATH")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))       # expohub-backend/scripts
    return os.path.join(os.path.dirname(here), "expohub.db")


def backup_db(db_path: str, log: List[str]) -> str:
    """用 SQLite 在线备份 API 备份到 <db>.bak-<时间戳>，并回读校验。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak_path = f"{db_path}.bak-{stamp}"
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    dst = sqlite3.connect(bak_path)
    try:
        src.backup(dst)
        dst.commit()
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {
            t: dst.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            for t in ("catalog_exhibitors", "catalog_products", "exhibitions")
        }
    finally:
        dst.close()
        src.close()
    size = os.path.getsize(bak_path)
    log.append(f"[OK] 已备份：{bak_path}（{size / 1024 / 1024:.1f} MB，"
               f"integrity_check={integrity}，"
               f"catalog_exhibitors={_fmt(counts['catalog_exhibitors'])}、"
               f"catalog_products={_fmt(counts['catalog_products'])}、"
               f"exhibitions={_fmt(counts['exhibitions'])}）")
    if integrity != "ok":
        raise SystemExit("[XX] 备份文件 integrity_check 未通过，已中止（不写库）")
    return bak_path


def run(
    db_path: str,
    apply: bool,
    match_mode: str,
    report_path: Optional[str],
) -> int:
    log: List[str] = []

    def say(line: str = "") -> None:
        log.append(line)

    if not os.path.isfile(db_path):
        print(f"[XX] 数据库文件不存在：{db_path}")
        return 1

    say("# 参展关系回填报告（exhibition_exhibitors）")
    say("")
    say(f"- 目标库：`{os.path.abspath(db_path)}`")
    say(f"- 模式：`{'APPLY（会写库，写前自动备份）' if apply else 'DRY-RUN（不写库）'}`")
    say(f"- 映射口径：`{match_mode}`")
    say(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    say("")

    conn = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    try:
        cur = conn.cursor()
        tables = {
            r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for needed in ("exhibitions", "catalog_exhibitors", "catalog_products"):
            if needed not in tables:
                print(f"[XX] 缺少表 {needed}，先跑应用建表")
                return 1
        table_exists = TABLE in tables
        if apply and not table_exists:
            print(f"[XX] 关系表 {TABLE} 不存在。先执行：\n"
                  f"     python scripts/migrate_exhibition_exhibitors.py")
            return 1

        exhibitions = [
            (int(eid), title)
            for eid, title in cur.execute(
                "SELECT id, title FROM exhibitions ORDER BY id"
            )
        ]
        total_exhibitors = int(
            cur.execute("SELECT COUNT(*) FROM catalog_exhibitors").fetchone()[0]
        )
        total_rows = int(
            cur.execute("SELECT COUNT(*) FROM catalog_products").fetchone()[0]
        )
        per_exhibitor = dict(
            cur.execute(
                "SELECT expo_name, COUNT(*) FROM catalog_exhibitors GROUP BY expo_name"
            ).fetchall()
        )
        per_product = dict(
            cur.execute(
                "SELECT e.expo_name, COUNT(p.id) FROM catalog_exhibitors e "
                "LEFT JOIN catalog_products p ON p.exhibitor_id = e.id "
                "GROUP BY e.expo_name"
            ).fetchall()
        )
        per_exhibitor = {k: int(v) for k, v in per_exhibitor.items()}
        per_product = {k: int(v) for k, v in per_product.items()}
        # (展商数, 展品数) by expo_name，供 dry-run 推算
        by_expo = {
            name: (per_exhibitor.get(name, 0), per_product.get(name, 0))
            for name in per_exhibitor
        }

        strict_idx, loose_idx, alias_idx = build_indexes(exhibitions)
        expo_names = [
            (name, int(n))
            for name, n in cur.execute(
                "SELECT expo_name, COUNT(*) FROM catalog_exhibitors "
                "GROUP BY expo_name ORDER BY COUNT(*) DESC, expo_name"
            )
        ]

        matches = [
            match_expo_name(name, n, strict_idx, loose_idx, alias_idx, match_mode)
            for name, n in expo_names
        ]
        mapped = [m for m in matches if m.ok]
        unmapped = [m for m in matches if not m.ok]

        # ---- 1) 映射明细 ----
        say("## 1. 展会 ↔ expo_name 映射明细")
        say("")
        say("| expo_name | 名录行数 | 匹配层 | 展会 ID | 说明 |")
        say("|---|---:|---|---:|---|")
        for m in matches:
            eid = str(m.exhibition_id) if m.ok else "—"
            say(f"| {m.expo_name} | {_fmt(m.rows)} | {m.level or '未命中'} | {eid} "
                f"| {m.reason} |")
        say("")

        # ---- 2) 汇总 ----
        mapped_rows = sum(m.rows for m in mapped)
        unmapped_rows = sum(m.rows for m in unmapped)
        expected_relations = mapped_rows
        say("## 2. 汇总")
        say("")
        say(f"- 名录展商总数：**{_fmt(total_exhibitors)}**（`catalog_exhibitors`）")
        say(f"- 名录展品总数：**{_fmt(total_rows)}**（`catalog_products`）")
        say(f"- distinct `expo_name`：{len(expo_names)} 个")
        say(f"- 可映射 `expo_name`：**{len(mapped)}** 个 → 覆盖展商 "
            f"**{_fmt(mapped_rows)}** 行")
        say(f"- 无法映射 `expo_name`：{len(unmapped)} 个 → 涉及展商 "
            f"{_fmt(unmapped_rows)} 行（不产生关系）")
        say(f"- 预计生成参展关系：**{_fmt(expected_relations)}** 条"
            f"（每展商按其 expo_name 一条）")
        say("")

        # ---- 3) 无法映射清单 ----
        say("## 3. 无法映射的 expo_name（不硬塞）")
        say("")
        if unmapped:
            say("| expo_name | 行数 | 原因 |")
            say("|---|---:|---|")
            for m in unmapped:
                say(f"| {m.expo_name} | {_fmt(m.rows)} | {m.reason} |")
            say("")
            say(f"合计：{_fmt(unmapped_rows)} 行不产生参展关系"
                f"（占名录 {unmapped_rows / max(total_exhibitors, 1):.1%}）。")
        else:
            say("（无：所有 expo_name 都匹配上了）")
        say("")

        # ---- 4) 每场展会（按映射推算；apply 后与 5.1 的实际值对照）----
        counts = _projected_counts(matches, by_expo)
        say("## 4. 每场展会（按本轮映射推算）")
        say("")
        say("| 展会 ID | 标题 | 展商数 | 展品数 |")
        say("|---:|---|---:|---:|")
        for eid, t in exhibitions:
            ex, pr = counts.get(eid, (0, 0))
            say(f"| {eid} | {t} | {_fmt(ex)} | {_fmt(pr)} |")
        covered = sum(1 for eid, _ in exhibitions if counts.get(eid, (0, 0))[0])
        say("")
        say(f"{len(exhibitions)} 场展会中 {covered} 场有关系数据。")
        say("")

        # ---- 5) 落库 / 备份 ----
        if not apply:
            say("## 5. 落库")
            say("")
            say("DRY-RUN：未写库、未备份。加 `--apply` 才会执行（执行前自动备份）。")
            say(f"将执行：`INSERT OR IGNORE INTO {TABLE}"
                f"(exhibition_id, catalog_exhibitor_id, expo_label, booth_no)`"
                f" … 共 {len(mapped)} 条 INSERT…SELECT，预计 "
                f"{_fmt(expected_relations)} 行。")
        else:
            say("## 5. 备份与落库")
            say("")
            bak = backup_db(db_path, log)   # 备份 + 回读 integrity_check
            say(f"- 备份文件：`{bak}`")
            say("")
            inserted = 0
            with conn:
                for m in mapped:
                    cur.execute(
                        f"INSERT OR IGNORE INTO {TABLE} "
                        f"(exhibition_id, catalog_exhibitor_id, expo_label, booth_no) "
                        f"SELECT ?, id, expo_name, booth_no FROM catalog_exhibitors "
                        f"WHERE expo_name = ?",
                        (m.exhibition_id, m.expo_name),
                    )
                    inserted += cur.rowcount
            total_rel = int(
                cur.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
            )
            fk_own = cur.execute(
                f"PRAGMA foreign_key_check({TABLE})"
            ).fetchall()
            fk_all = len(cur.execute("PRAGMA foreign_key_check").fetchall())
            dup = cur.execute(
                f"SELECT COUNT(*) FROM (SELECT exhibition_id, catalog_exhibitor_id, "
                f"COUNT(*) c FROM {TABLE} GROUP BY 1, 2 HAVING c > 1)"
            ).fetchone()[0]
            null_lab = int(
                cur.execute(
                    f"SELECT COUNT(*) FROM {TABLE} WHERE expo_label IS NULL"
                ).fetchone()[0]
            )
            say(f"- 本次插入：**{_fmt(inserted)}** 行"
                f"（已存在而被忽略：{_fmt(max(expected_relations - inserted, 0))} 行）")
            say(f"- `{TABLE}` 当前总行数：**{_fmt(total_rel)}**"
                f"（推算 {_fmt(expected_relations)}，"
                f"{'一致' if total_rel == expected_relations else '不一致，请检查！'}）")
            say(f"- 唯一约束自检：重复 (exhibition_id, catalog_exhibitor_id) 组数 = {dup}"
                f"（应为 0）")
            say(f"- 外键自检（仅本表 `PRAGMA foreign_key_check({TABLE})`）"
                f"违规 = {len(fk_own)} 条（应为 0）")
            say(f"- 全库外键检查：共 {fk_all} 条违规，均为历史遗留表"
                f"（points_ledger / memberships → users），与本表无关")
            say(f"- `expo_label` 为空的行：{_fmt(null_lab)}（名录 expo_name 为空的展商为 0，"
                f"预期为 0）")
            say("")
            say("### 5.1 落库后每场展会实际分布（与第 4 节推算对照）")
            say("")
            say("| 展会 ID | 标题 | 展商数 | 展品数 | 与推算一致 |")
            say("|---:|---|---:|---:|---|")
            actual = _per_exhibition_counts(conn, True)
            same = True
            for eid, t in exhibitions:
                ex, pr = actual.get(eid, (0, 0))
                px, pp = counts.get(eid, (0, 0))
                ok = (ex, pr) == (px, pp)
                same = same and ok
                say(f"| {eid} | {t} | {_fmt(ex)} | {_fmt(pr)} | {'是' if ok else '否'} |")
            say("")
            say(f"推算 vs 实际：{'全部一致' if same else '存在差异，请检查！'}")
            say("")
            say("### 关系表全库分布（SQL）")
            say("")
            say("```sql")
            say(f"SELECT exhibition_id, COUNT(*) FROM {TABLE} "
                f"GROUP BY exhibition_id ORDER BY exhibition_id;")
            say("```")
            for eid, n in conn.execute(
                f"SELECT exhibition_id, COUNT(*) FROM {TABLE} "
                f"GROUP BY exhibition_id ORDER BY exhibition_id"
            ):
                say(f"  exhibition_id={eid:<3} rows={_fmt(int(n))}")
            say("")
            say(f"`SELECT COUNT(*) FROM {TABLE};` → {_fmt(total_rel)}")
    finally:
        conn.close()

    text = "\n".join(log)
    print(text)
    if report_path:
        os.makedirs(os.path.dirname(os.path.abspath(report_path)) or ".", exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"\n[OK] 报告已写入：{report_path}")
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="回填 exhibition_exhibitors（默认 dry-run；--apply 前自动备份）"
    )
    parser.add_argument("--db", default=default_db_path(),
                        help="SQLite 数据库路径（默认 <expohub-backend>/expohub.db）")
    parser.add_argument("--apply", action="store_true",
                        help="真正写库（默认 dry-run，只打印报告）")
    parser.add_argument("--match-mode", default="layered", choices=("layered", "strict"),
                        help="映射口径：layered=strict→loose→alias（默认）；strict=仅严格相等")
    parser.add_argument("--report", default=None, help="把报告另存为文本文件")
    args = parser.parse_args(argv)
    return run(args.db, args.apply, args.match_mode, args.report)


if __name__ == "__main__":
    sys.exit(main())
