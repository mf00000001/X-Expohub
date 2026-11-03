"""
分期展的期次抽取（广交会这类：一个展拆成 3 期，各期日期、展区都不同）。

为什么必须单独建表：
`expo.start_date / end_date` 是一对字段，装不下"10-15~19 / 10-23~27 / 10-31~11-04"。
批次 1 当时只能把其中一期的日期写进去，另外两期直接丢失——而且丢得**看不出来**，
因为表里看着是"有日期"的。对展商来说这是致命信息：他要报的是第二期，
系统却告诉他第一期的档期。

产出 `data/batch1/phases.json`，由 load_persona.py 灌进 expo_phase。

用法：
    python scripts/persona/extract_phases.py
    python scripts/persona/extract_phases.py --only canton-fair
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_extract import _norm_sep, all_ids, load_body  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "batch1" / "phases.json"

# "第一期 先进制造" / "第 2 期" / "Phase 1"
_PHASE = re.compile(r"第\s*([一二三四五六1-6])\s*期|Phase\s*([1-6])\b", re.I)
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}

# 日期区间：2026年10月15日-19日 / 2026年10月31日-11月4日 / 2026.10.15-19
_RANGE = re.compile(
    r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?\s*[-—~至到]\s*"
    r"(?:(20\d{2})\s*[年./-]\s*)?(?:(\d{1,2})\s*[月./-]\s*)?(\d{1,2})\s*日?")

# 期次名：紧跟"第X期"后面的 2~8 个中文字，如"先进制造""品质家居"
_PHASE_NAME = re.compile(r"第\s*[一二三四五六1-6]\s*期\s*([\u4e00-\u9fff]{2,8})")


def parse_phases(body: str) -> list[dict]:
    flat = re.sub(r"[ \t]+", " ", _norm_sep(body))
    marks = [(m.start(), m.end(),
              int(_CN_NUM.get(m.group(1), 0) or m.group(2) or 0)) for m in _PHASE.finditer(flat)]
    if len(marks) < 2:          # 只有一个"第N届/期"的噪声不算分期展
        return []

    out = []
    for i, (s, e, no) in enumerate(marks):
        # 每个期次只在"到下一个期次标记"之间找日期，避免把别期的日期抢过来
        nxt = marks[i + 1][0] if i + 1 < len(marks) else min(len(flat), e + 400)
        window = flat[e:nxt]
        m = _RANGE.search(window)
        if not m:
            continue
        y1, mo1, d1, y2, mo2, d2 = m.groups()
        end_year = int(y2 or y1)
        end_month = int(mo2 or mo1)
        rec = {
            "phase_no": no,
            "phase_name": None,
            "start_date": "%04d-%02d-%02d" % (int(y1), int(mo1), int(d1)),
            "end_date": "%04d-%02d-%02d" % (end_year, end_month, int(d2)),
            "evidence": m.group(0),
        }
        nm = _PHASE_NAME.search(flat, s, e + 12)
        if nm:
            rec["phase_name"] = nm.group(1)[:20]
        out.append(rec)

    # 期次号去重（同一期可能出现多次），保留第一个有日期的
    seen, uniq = set(), []
    for r in out:
        if r["phase_no"] in seen:
            continue
        seen.add(r["phase_no"])
        uniq.append(r)
    return sorted(uniq, key=lambda r: r["start_date"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    ids = all_ids()
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        ids = [i for i in ids if i in want]

    recs = []
    for rid in ids:
        body = load_body(rid)
        if not body:
            continue
        ph = parse_phases(body)
        if len(ph) >= 2:
            recs.append({"id": rid, "phases": ph})
            print("  %-20s %d 期：%s" % (rid, len(ph), " / ".join(
                "%s %s~%s" % (p["phase_name"] or ("第%d期" % p["phase_no"]),
                              p["start_date"], p["end_date"]) for p in ph)))

    OUT.write_text(json.dumps({"built_at": json.dumps(__import__("datetime").datetime.now().isoformat()),
                               "total": len(recs), "records": recs},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n检出分期展 %d 个 → %s" % (len(recs), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
