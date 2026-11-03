"""
批次 1c：把规则抽取（skeleton.json）与 LLM 抽取（llm_extract.json）合并成一份可用数据集。

合并原则——**不是"两边取并集"，而是按可信度分层**：

  1. jsonld（schema.org Event）> LLM > 词典 > 正则
     · jsonld 是站点自己声明的结构化数据，规则和模型都可能读错，它不会
     · LLM 要求带 evidence 且机器核验过，比正则的"可能抽到营销句"可靠
     · venue 例外：词典是人工维护的 32 个展馆，命中即真，优先于 LLM
  2. 两源一致 → conf 升为 high（独立来源互相印证，这是最强证据）
  3. 两源冲突 → **不猜**。按上面优先级取一个，但把另一个记进 conflicts，
     因为冲突本身就是最有价值的数据：它精确指出规则哪一处抽错了

输出 merged.json，保留每个字段的 method 与 evidence，下游能点回原文。

用法：
    python scripts/persona/merge_fields.py
    python scripts/persona/merge_fields.py --verbose
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BATCH = ROOT / "data" / "batch1"

FIELDS = ("title", "start_date", "end_date", "prev_start_date", "prev_end_date",
          "venue", "city", "organizer", "edition", "deadline")

# 数值越小越可信
RANK = {"jsonld": 0, "llm": 1, "dict": 2, "config": 3, "title_tag": 3, "regex": 4}


def _rank(f: dict) -> int:
    return RANK.get(f.get("method", "regex"), 9)


def _same(a, b) -> bool:
    return str(a).strip() == str(b).strip()


def merge_one(reg: dict, llm: dict | None) -> dict:
    rf = reg.get("fields", {}) or {}
    lf = (llm or {}).get("fields", {}) or {}
    out: dict = {}
    conflicts: list[dict] = []

    for k in FIELDS:
        a, b = rf.get(k), lf.get(k)
        if a is None and b is None:
            continue

        # 展馆：人工词典优先。32 个展馆名是维护过的，LLM 偶尔会把"上海新国际
        # 博览中心"写成"上海新国际展览中心"，一字之差但下游按名字匹配就断了。
        if k == "venue" and a and a.get("method") == "dict":
            out[k] = a
            if b and not _same(a["value"], b["value"]):
                conflicts.append({"field": k, "kept": a["value"], "kept_src": "dict",
                                  "other": b["value"], "other_src": "llm", "note": "词典优先"})
            continue

        if a is None:
            out[k] = b
            continue
        if b is None:
            out[k] = a
            continue

        if _same(a["value"], b["value"]):
            merged = dict(a)
            merged["conf"] = "high"
            merged["also"] = "llm 一致"
            out[k] = merged
            continue

        # 冲突：按可信度取
        win, lose = (a, b) if _rank(a) <= _rank(b) else (b, a)
        out[k] = win
        conflicts.append({
            "field": k, "kept": win["value"], "kept_src": win.get("method"),
            "other": lose["value"], "other_src": lose.get("method"),
            "other_evidence": (lose.get("evidence") or "")[:60],
        })

    # 日期归属自检：current 与 prev 不能互相冒充
    today = date.today()
    for cur, prv in (("start_date", "prev_start_date"), ("end_date", "prev_end_date")):
        if cur in out and prv in out:
            try:
                c = date.fromisoformat(str(out[cur]["value"])[:10])
                p = date.fromisoformat(str(out[prv]["value"])[:10])
            except ValueError:
                continue
            if c < today:
                out.pop(cur, None)
                conflicts.append({"field": cur, "kept": None, "kept_src": "guard",
                                  "other": c.isoformat(), "other_src": "merged",
                                  "note": "本届日期已过，已剔除"})
            elif p >= today:
                out.pop(prv, None)

    return {"fields": out, "conflicts": conflicts}


def dates_status_of(fields: dict) -> str:
    """按**合并后**的字段重算日期三态。

    不能直接沿用采集层的 dates_status：19 个纯前端站的规则层什么也没抽到
    （状态是 none），但渲染后由 LLM 补出了日期。沿用旧状态会让下游看到
    "有 start_date 却标着 none"的自相矛盾记录。
    """
    if "start_date" in fields:
        return "current"
    if "prev_start_date" in fields:
        return "past"
    return "none"


def detect_phases(rid: str) -> int:
    """数一数这个展分几期。

    广交会官网写着"第一期 10.15-19 / 第二期 10.23-27 / 第三期 10.31-11.4"，
    而 start_date/end_date 只有一对字段，只能装下第一期。
    结果就是：今天（11-03）第三期正在办，系统却判成"已结束"。

    这不是抽取错误，是数据模型装不下。在加 `expo_phase` 子表之前，
    至少要把"这个展分 N 期"标出来——否则下游会拿一期日期当整个展期用。
    """
    for d in (BATCH / "rendered", BATCH / "raw"):
        p = d / f"{rid}.txt"
        if p.exists():
            try:
                t = p.read_text(encoding="utf-8")
            except OSError:
                return 0
            hits = set(re.findall(r"第\s*([一二三四五六七八九十\d])\s*期", t))
            return len(hits) if len(hits) >= 2 else 0
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    sk = json.loads((BATCH / "skeleton.json").read_text(encoding="utf-8"))
    llm_path = BATCH / "llm_extract.json"
    llm_recs = {}
    if llm_path.exists():
        for r in json.loads(llm_path.read_text(encoding="utf-8")).get("records", []):
            llm_recs[r["id"]] = r
    else:
        print("! 没有 llm_extract.json，只输出规则结果", file=sys.stderr)

    results = []
    gained: dict[str, int] = {}
    for rec in sk["records"]:
        m = merge_one(rec, llm_recs.get(rec["id"]))
        rf = rec.get("fields", {})
        for k in m["fields"]:
            if k not in rf:
                gained[k] = gained.get(k, 0) + 1
        st = dates_status_of(m["fields"])
        typical = rec.get("typical_month")
        # 往届日期若由 LLM 补出，采集层那时是空的，月份要跟着重算
        if typical is None and st == "past":
            try:
                typical = date.fromisoformat(
                    str(m["fields"]["prev_start_date"]["value"])[:10]).month
            except (KeyError, ValueError):
                typical = None
        results.append({
            "id": rec["id"], "name": rec.get("name"), "url": rec.get("url"),
            "layer": rec.get("layer"), "category": rec.get("category"),
            "dates_status": st,
            "typical_month": typical,
            "phases": detect_phases(rec["id"]),
            "fields": m["fields"], "conflicts": m["conflicts"],
            "error": rec.get("error"),
        })

    ok = [r for r in results if not r.get("error")]
    fill = {k: sum(1 for r in ok if k in r["fields"]) for k in FIELDS}
    src: dict[str, dict[str, int]] = {}
    for r in ok:
        for k, v in r["fields"].items():
            src.setdefault(k, {}).setdefault(v.get("method", "?"), 0)
            src[k][v.get("method", "?")] += 1

    all_conf = [(r["id"], c) for r in results for c in r["conflicts"]]
    out = {
        "built_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results), "ok": len(ok),
        "fill": fill,
        "fill_rate": {k: round(v / len(ok), 3) for k, v in fill.items()} if ok else {},
        "by_source": src,
        "gained_from_llm": gained,
        "conflict_count": len(all_conf),
        "records": results,
    }
    (BATCH / "merged.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 62)
    print("合并完成：%d 个展会（可用 %d）" % (len(results), len(ok)))
    print("=" * 62)
    print("%-14s %5s %6s  %s" % ("字段", "有值", "填充率", "来源"))
    for k in FIELDS:
        s = " ".join("%s×%d" % (m, n) for m, n in sorted(src.get(k, {}).items(), key=lambda x: -x[1]))
        print("%-14s %5d %5.0f%%  %s" % (k, fill[k], 100 * fill[k] / max(len(ok), 1), s))

    if gained:
        print("\nLLM 净救回的字段（规则完全抽不到的）：")
        for k, n in sorted(gained.items(), key=lambda x: -x[1]):
            print("  %-14s +%d" % (k, n))

    print("\n两源冲突 %d 处（按字段）：" % len(all_conf))
    cby: dict[str, int] = {}
    for _, c in all_conf:
        cby[c["field"]] = cby.get(c["field"], 0) + 1
    for k, n in sorted(cby.items(), key=lambda x: -x[1]):
        print("  %-14s %d" % (k, n))

    if args.verbose:
        print("\n冲突明细：")
        for rid, c in all_conf[:40]:
            print("  %-20s %-13s 保留 %-22r(%s)  舍弃 %-22r(%s)" % (
                rid, c["field"], str(c["kept"])[:22], c.get("kept_src"),
                str(c["other"])[:22], c.get("other_src")))

    print("\n→ %s" % (BATCH / "merged.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
