"""
把批次 1（骨架/日期/场馆）与批次 2（规模/属性）的抽取结果装进画像库 persona.db。

为什么要有这一层：
前面几批的产物都是 data/batch*/ 下的 JSON，各自正确但**互相孤立**——
下游算 E1（客群可得性）要同时读日期、观众数、展商数，还得知道每个数的口径，
翻三个文件拼字段迟早会拼错。这里做一次统一落库，`expo` 表一行就是一个展，
`expo_observation` 保留每个字段的原文依据与口径，随时可以回溯到网页原句。

设计约束：
· **幂等**：同一个 slug 重复导入只更新，不产生重复展；每次导入的观测记录
  按 (expo_id, batch_id) 先删后插，重跑不会翻倍。
· **不猜**：某个字段没有就是 NULL，不用 0 或默认值填。
· **口径不丢**：visitor_count 和 visitor_caliber 必须成对写入，
  只写数字的 30 万和 55 万会被下游当成同一种量级来比。

用法：
    python scripts/persona/load_persona.py            # 导入并打印核对
    python scripts/persona/load_persona.py --dry-run  # 只看会写什么，不落库
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "persona.db"
MERGED = ROOT / "data" / "batch1" / "merged.json"
SCALE = ROOT / "data" / "batch2" / "scale.json"
PHASES = ROOT / "data" / "batch1" / "phases.json"

_CJK = re.compile(r"[\u4e00-\u9fff]")

# expo 表里由批次 1/2 负责的列
FIELD_MAP = {
    # merged.json → expo
    "city": "city", "venue": "venue_name",
    "start_date": "start_date", "end_date": "end_date", "edition": "edition_no",
    # scale.json → expo
    "admission": "audience_access", "nature": "biz_type",
    "visitor_count": "visitor_count", "exhibitor_count": "exhibitor_count",
    "exhibition_area": "exhibit_area_sqm",
}
CALIBER_OF = {                      # 数值字段 → 口径列
    "visitor_count": "visitor_caliber",
    "exhibitor_count": "exhibitor_caliber",
    "exhibition_area": "area_caliber",
}
_CONF_RANK = {"high": 3, "medium": 2, "low": 1}
_LETTER = {3: "H", 2: "M", 1: "L"}


def _int_or_none(v):
    try:
        n = int(float(v))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _edition(v):
    if v is None:
        return None
    m = re.search(r"\d+", str(v))
    return int(m.group(0)) if m else None


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("records", [])


def build() -> tuple[list[dict], list[dict], dict]:
    """把两个批次合并成"一行一个展"的结构 + 观测流水。"""
    merged = {r["id"]: r for r in _load(MERGED)}
    scale = {r["id"]: r for r in _load(SCALE)}
    phases = {r["id"]: r["phases"] for r in _load(PHASES)}
    ids = sorted(set(merged) | set(scale))

    rows, obs = [], []
    for rid in ids:
        m = merged.get(rid, {})
        s = scale.get(rid, {})
        mf, sf = m.get("fields") or {}, s.get("fields") or {}

        row: dict = {"slug": rid, "source_exhibition_id": None}
        confs: list[int] = []

        def put(key: str, cell: dict, column: str, cast=None, weigh: bool = True):
            v = cell.get("value")
            if cast:
                v = cast(v)
            if v is None:
                return
            row[column] = v
            # 整体置信度只由"日期 + 数值"决定。准入/性质这类判断型字段
            # 天生证据弱（正文很少明说），把它们算进来会让一个数据齐全的展
            # 整体被打成 L——那是把"两个软字段"的锅甩给了整条记录。
            if weigh:
                confs.append(_CONF_RANK.get(cell.get("conf", "low"), 1))

        for src_key, col in FIELD_MAP.items():
            cell = mf.get(src_key) or sf.get(src_key)
            if not cell:
                continue
            put(src_key, cell, col, _edition if src_key == "edition" else None,
                weigh=src_key not in ("admission", "nature"))

        for f in ("visitor_count", "exhibitor_count", "exhibition_area"):
            cell = sf.get(f)
            if not cell:
                continue
            put(f, cell, FIELD_MAP[f], _int_or_none)
            if cell.get("caliber"):
                row[CALIBER_OF[f]] = cell["caliber"]
            if f == "visitor_count" and cell.get("raw_text"):
                row["visitor_count_raw"] = cell["raw_text"][:120]

        # 分期展：主档的 start/end 只能是"整个会期"的外沿（最早一期开幕 → 最晚一期闭幕），
        # 具体报哪一期看 expo_phase。合并层可能只抽到某一期的日期，
        # 所以这里用期次数据覆盖，而不是反过来。
        ph = phases.get(rid) or []
        if len(ph) >= 2:
            row["start_date"] = min(p["start_date"] for p in ph)
            row["end_date"] = max(p["end_date"] for p in ph)
            row["_phases"] = ph

        # name_cn 是 NOT NULL，英文站没有中文名也得有主名：中文名缺失时
        # 用原标题兜底，纯英文的再额外写一份 name_en，别让"没有中文名"变成"没有名字"。
        title = (mf.get("title") or {}).get("value") or ""
        if title:
            row["name_cn"] = title[:200]
            if not _CJK.search(title):
                row["name_en"] = title[:200]
        else:
            row["name_cn"] = rid

        # 数据状态：规模三件套齐全=full，有日期或规模=partial，其余=skeleton
        have = sum(1 for c in ("visitor_count", "exhibitor_count", "exhibit_area_sqm")
                   if row.get(c))
        if have == 3:
            row["data_status"] = "full"
        elif have or row.get("start_date"):
            row["data_status"] = "partial"
        else:
            row["data_status"] = "skeleton"
        row["confidence_overall"] = _LETTER.get(min(confs), "L") if confs else None
        row["has_listing"] = 0             # NOT NULL；名录数据要到批次 3 才有
        row["sample_group"] = m.get("layer")

        notes = []
        if m.get("dates_status"):
            notes.append("dates=" + m["dates_status"])
        if m.get("phases"):
            notes.append("分%d期" % m["phases"])
        if s.get("text_note"):
            notes.append("口径备注:" + s["text_note"][:160])
        if s.get("review"):
            notes.append("需复核")
        row["note"] = " | ".join(notes)[:900] or None
        rows.append(row)

        # 观测流水：优先保留"有依据"的字段，证据缺失的也留一条空证据记录，
        # 这样"这个字段抽到了但依据丢了"是可查的，而不是悄悄消失。
        url = m.get("url")
        for src_key in ("title", "start_date", "end_date", "venue", "city",
                        "organizer", "edition", "deadline"):
            cell = mf.get(src_key)
            if cell:
                obs.append(dict(slug=rid, field_key=src_key, cell=cell, url=url, batch="b1"))
        for f in ("visitor_count", "exhibitor_count", "exhibition_area",
                  "prev_visitor_count", "prev_exhibitor_count", "prev_area",
                  "admission", "nature"):
            cell = sf.get(f)
            if cell:
                obs.append(dict(slug=rid, field_key=f, cell=cell, url=url, batch="b2"))

    summary = {
        "expo": len(rows),
        "with_date": sum(1 for r in rows if r.get("start_date")),
        "with_visitor": sum(1 for r in rows if r.get("visitor_count")),
        "with_exhibitor": sum(1 for r in rows if r.get("exhibitor_count")),
        "with_area": sum(1 for r in rows if r.get("exhibit_area_sqm")),
        "observation": len(obs),
    }
    return rows, obs, summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows, obs, summary = build()
    print("待写入：%d 个展｜其中 有日期 %d / 有观众数 %d / 有展商数 %d / 有面积 %d｜观测 %d 条"
          % (summary["expo"], summary["with_date"], summary["with_visitor"],
             summary["with_exhibitor"], summary["with_area"], summary["observation"]))
    if args.dry_run:
        for r in rows[:3]:
            print(" ", {k: v for k, v in r.items() if v is not None})
        return 0

    if not DB.exists():
        print("✗ 找不到 %s，先跑 init_db.py" % DB, file=sys.stderr)
        return 2

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    cur.execute("INSERT INTO import_batch (filename, row_count, inserted, updated, skipped,"
                " failed, operator, note, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                ("merged.json+scale.json", len(rows), 0, 0, 0, 0, "script",
                 "批次1+批次2 合并导入", now))
    batch_id = cur.lastrowid

    ins = upd = 0
    phase_rows: list[tuple[int, dict]] = []
    for r in rows:
        slug = r.pop("slug")
        for p in r.pop("_phases", []):
            phase_rows.append((slug, p))
        cur.execute("SELECT id FROM expo WHERE slug=?", (slug,))
        got = cur.fetchone()
        r["updated_at"] = now
        if got:
            expo_id = got[0]
            sets = ", ".join("%s=?" % k for k in r)
            cur.execute("UPDATE expo SET %s WHERE id=?" % sets, list(r.values()) + [expo_id])
            upd += 1
        else:
            r["created_at"] = now
            cols = ", ".join(r)
            cur.execute("INSERT INTO expo (slug, %s) VALUES (%s)"
                        % (cols, ",".join("?" * (len(r) + 1))), [slug] + list(r.values()))
            expo_id = cur.lastrowid
            ins += 1
        r["slug"] = slug
        id_of[slug] = expo_id

    # 观测表存的是**当前快照**，不是历史流水：每次导入先清掉这批展的旧观测再插。
    # 若按 batch_id 删，重跑一次就会留下两份一模一样的数据，
    # 下游 count 或 join 会凭空翻倍。历史由 import_batch 记录。
    cur.executemany("DELETE FROM expo_observation WHERE expo_id=?", [(i,) for i in id_of.values()])
    for o in obs:
        cell = o["cell"]
        cur.execute(
            "INSERT INTO expo_observation (expo_id, field_key, raw_text, num_value, unit,"
            " caliber, source_url, source_type, fetched_at, confidence, batch_id, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (id_of[o["slug"]], o["field_key"], str(cell.get("raw_text") or cell.get("value") or "")[:300],
             cell.get("value") if isinstance(cell.get("value"), (int, float)) else None,
             str(cell.get("unit") or "")[:20] or None, str(cell.get("caliber") or "")[:40] or None,
             o["url"], "web" if o["url"] else "manual", now,
             str(cell.get("conf") or "")[:5] or None, batch_id, now))

    # 期次：先清后插，保证重跑不翻倍（与观测表同一套幂等策略）
    expo_ids = list(id_of.values())
    if expo_ids:
        cur.executemany("DELETE FROM expo_phase WHERE expo_id=?", [(i,) for i in expo_ids])
    for slug, p in phase_rows:
        cur.execute(
            "INSERT INTO expo_phase (expo_id, phase_no, phase_name, start_date, end_date,"
            " zone_hint, evidence, confidence, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (id_of[slug], p.get("phase_no"), p.get("phase_name"), p.get("start_date"),
             p.get("end_date"), p.get("zone_hint"), str(p.get("evidence") or "")[:300],
             "medium", now))

    cur.execute("UPDATE import_batch SET inserted=?, updated=? WHERE id=?", (ins, upd, batch_id))
    con.commit()

    print("\n落库完成：新增 %d，更新 %d，观测 %d 条（batch_id=%d）" % (ins, upd, len(obs), batch_id))
    for tb in ("expo", "expo_observation", "expo_phase", "import_batch"):
        n = con.execute("SELECT COUNT(*) FROM %s" % tb).fetchone()[0]
        print("  %-18s %d 行" % (tb, n))
    con.close()
    return 0


id_of: dict[str, int] = {}

if __name__ == "__main__":
    sys.exit(main())
