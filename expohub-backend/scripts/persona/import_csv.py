"""
人工录入通道（CSV 进、画像库出）。

为什么必须有这条通道：
批次 1 实测有 18 个站的官网**真的不写展期**（只在公众号发），另有 10~14 个站
首页只有导航、数据在需要登录的名录页里。技术手段到这里就到头了，
继续硬啃的成本远高于人工确认 5 分钟。

这条通道的两个职责：
1. `--template` 按"缺什么"生成待办表，已有的值预先填好，人只需要补空格
2. `--load` 校验后写库，**并且拒绝静默通过**：日期格式错、结束早于开始、
   数字为负、slug 不存在，一律逐行报错并跳过，不会"看着成功其实没进"

人工录入的置信度是 high：人已经对着官网核过了。但要留痕——source_type 记 manual，
operator 记在 import_batch 里，出问题能追。

用法：
    python scripts/persona/import_csv.py --template
    python scripts/persona/import_csv.py --load data/manual/todo.csv --operator 牛强
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "persona.db"
MANUAL = ROOT / "data" / "manual"

# 列顺序即模板顺序。slug 是唯一键，name_cn 只读参考，其余可填。
COLS = ["slug", "name_cn", "city", "venue_name", "start_date", "end_date",
        "edition_no", "visitor_count", "visitor_caliber", "exhibitor_count",
        "exhibitor_caliber", "exhibit_area_sqm", "area_caliber",
        "audience_access", "biz_type", "booth_deadline", "source_url", "operator_note"]

CALIBERS = {
    "visitor_caliber": {"visit", "person", "registered", "unknown"},
    "exhibitor_caliber": {"company", "brand", "booth", "unknown"},
    "area_caliber": {"gross", "net"},
    "audience_access": {"trade_only", "public", "mixed"},
    "biz_type": {"B2B", "B2C", "mixed"},
}
NUM_COLS = ("visitor_count", "exhibitor_count", "exhibit_area_sqm", "edition_no")
# 数值列 → 口径列，落观测时口径要跟着走，否则将来查这条数不知道是人次还是人数
CAL_OF = {"visitor_count": "visitor_caliber", "exhibitor_count": "exhibitor_caliber",
          "exhibit_area_sqm": "area_caliber"}


def make_template() -> Path:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    MANUAL.mkdir(parents=True, exist_ok=True)
    out = MANUAL / "todo.csv"

    rows = list(con.execute("""
        SELECT e.*, p.ratio_band FROM expo e
        LEFT JOIN expo_persona p ON p.expo_id = e.id
        ORDER BY (e.start_date IS NULL) DESC, e.slug
    """))
    # 只把"还有空"的展放进待办：日期、观众、展商、面积全有的不需要人管
    gap = [r for r in rows if not r["start_date"] or not r["end_date"]
           or not r["visitor_count"] or not r["exhibitor_count"] or not r["exhibit_area_sqm"]]

    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in gap:
            w.writerow({
                "slug": r["slug"], "name_cn": r["name_cn"] or "",
                "city": r["city"] or "", "venue_name": r["venue_name"] or "",
                "start_date": r["start_date"] or "", "end_date": r["end_date"] or "",
                "edition_no": r["edition_no"] or "",
                "visitor_count": r["visitor_count"] or "",
                "visitor_caliber": r["visitor_caliber"] or "",
                "exhibitor_count": r["exhibitor_count"] or "",
                "exhibitor_caliber": r["exhibitor_caliber"] or "",
                "exhibit_area_sqm": r["exhibit_area_sqm"] or "",
                "area_caliber": r["area_caliber"] or "",
                "audience_access": r["audience_access"] or "",
                "biz_type": r["biz_type"] or "",
                "booth_deadline": r["booth_deadline"] or "",
                "source_url": "", "operator_note": "",
            })
    con.close()
    print("待办表：%d 个展（共 %d）→ %s" % (len(gap), len(rows), out))
    miss_date = sum(1 for r in gap if not r["start_date"])
    print("  其中缺展期 %d 个、缺观众数 %d 个、缺面积 %d 个" % (
        miss_date, sum(1 for r in gap if not r["visitor_count"]),
        sum(1 for r in gap if not r["exhibit_area_sqm"])))
    return out


def _iso(s: str) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    s = s.replace("/", "-").replace(".", "-")
    try:
        return date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        raise ValueError("日期不是 YYYY-MM-DD：%r" % s)


def validate(row: dict) -> tuple[dict, list[str]]:
    """返回 (清洗后的更新字段, 错误列表)。有任何错误就整行跳过。"""
    errs: list[str] = []
    upd: dict = {}

    # source_url 只进观测表，不下写 expo（expo 没有这一列）——
    # 之前把它塞进 upd 就直接撞上 "no such column: source_url"。
    for c in ("city", "venue_name", "booth_deadline"):
        if (row.get(c) or "").strip():
            upd[c] = row[c].strip()[:200]

    for c in ("start_date", "end_date"):
        try:
            v = _iso(row.get(c, ""))
        except ValueError as e:
            errs.append(str(e))
            continue
        if v:
            upd[c] = v
    if "start_date" in upd and "end_date" in upd and upd["end_date"] < upd["start_date"]:
        errs.append("结束日早于开展日：%s > %s" % (upd["start_date"], upd["end_date"]))

    for c in NUM_COLS:
        raw = (row.get(c) or "").strip().replace(",", "")
        if not raw:
            continue
        try:
            n = int(float(raw))
        except ValueError:
            errs.append("%s 不是数字：%r" % (c, row.get(c)))
            continue
        if n <= 0:
            errs.append("%s 必须为正数：%d" % (c, n))
            continue
        upd[c] = n

    for c, allowed in CALIBERS.items():
        raw = (row.get(c) or "").strip().lower()
        if not raw:
            continue
        if raw not in allowed:
            errs.append("%s 只能是 %s，收到 %r" % (c, sorted(allowed), raw))
            continue
        upd[c] = raw

    # 口径必须成对：只给人次不给人次口径，等于把 2 倍的误差带进 E1
    for num, cal in (("visitor_count", "visitor_caliber"),
                     ("exhibitor_count", "exhibitor_caliber"),
                     ("exhibit_area_sqm", "area_caliber")):
        if num in upd and cal not in upd:
            errs.append("%s 有值但缺 %s（口径不能留空）" % (num, cal))

    return upd, errs


def load(path: Path, operator: str, db: Path = DB) -> int:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur = con.execute(
        "INSERT INTO import_batch (filename, row_count, inserted, updated, skipped, failed,"
        " operator, note, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (path.name, 0, 0, 0, 0, 0, operator or "manual", "人工录入", now))
    batch_id = cur.lastrowid

    ok = fail = skip = 0
    errors: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for i, row in enumerate(rows, 2):
        slug = (row.get("slug") or "").strip()
        if not slug:
            continue
        expo = con.execute("SELECT * FROM expo WHERE slug=?", (slug,)).fetchone()
        if not expo:
            errors.append("第 %d 行：slug 不存在 %r" % (i, slug))
            fail += 1
            continue

        upd, errs = validate(row)
        if errs:
            errors.append("第 %d 行（%s）：%s" % (i, slug, "；".join(errs)))
            fail += 1
            continue
        # 只写"人真的填了东西"的行；只回填了 slug 的空行不算
        if not upd:
            skip += 1
            continue

        sets = ", ".join("%s=?" % k for k in upd)
        con.execute("UPDATE expo SET %s, updated_at=? WHERE id=?" % sets,
                    list(upd.values()) + [now, expo["id"]])
        for k, v in upd.items():
            cal = upd.get(CAL_OF[k]) if k in CAL_OF else None
            con.execute(
                "INSERT INTO expo_observation (expo_id, field_key, raw_text, num_value, unit,"
                " caliber, source_url, source_type, fetched_at, confidence, batch_id, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (expo["id"], k, str(v)[:300], v if isinstance(v, (int, float)) else None,
                 None, cal, row.get("source_url") or None, "manual", now, "high",
                 batch_id, now))
        ok += 1

    con.execute("UPDATE import_batch SET row_count=?, inserted=?, skipped=?, failed=?"
                " WHERE id=?", (len(rows), ok, skip, fail, batch_id))
    con.commit()
    con.close()

    print("读入 %d 行：写入 %d，跳过（本来就是空）%d，失败 %d" % (len(rows), ok, skip, fail))
    for e in errors:
        print("  ✗", e)
    if fail:
        print("\n失败行已跳过，其余正常入库。改完再跑一次即可（幂等）。")
    return 0 if not fail else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", action="store_true")
    ap.add_argument("--load", default="")
    ap.add_argument("--operator", default="")
    ap.add_argument("--db", default="", help="覆盖画像库路径（测试用，别指向真库）")
    args = ap.parse_args()

    if args.template:
        make_template()
        return 0
    if args.load:
        p = Path(args.load)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            print("✗ 找不到 %s" % p, file=sys.stderr)
            return 2
        db = Path(args.db) if args.db else DB
        return load(p, args.operator, db)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
