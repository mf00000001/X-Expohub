"""
把查证结果合并回候选名单。

规则：
  confidence = high/medium → 直接采用，旧 URL 存进 prev_url 备查
  confidence = low         → 采用但标 needs_verify=true
  confidence = none / url 为空 → 保留原值，标 unresolved=true

不覆盖已有 official_name 之外的字段；city 只有在新值非空时才更新。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAND = ROOT / "data" / "expo_candidates_v1.json"
OUT = ROOT / "data" / "expo_candidates_v2.json"
BATCH0 = ROOT / "data" / "batch0"


def main() -> int:
    data = json.loads(CAND.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in data["expos"]}

    merged_files = sorted(BATCH0.glob("agent_urls_*.json"))
    if not merged_files:
        print("没有找到 agent_urls_*.json")
        return 1

    stats = {"high": 0, "medium": 0, "low": 0, "none": 0, "unknown_id": []}
    for f in merged_files:
        rows = json.loads(f.read_text(encoding="utf-8"))
        for r in rows:
            eid = r.get("id")
            e = by_id.get(eid)
            if e is None:
                stats["unknown_id"].append(eid)
                continue
            conf = (r.get("confidence") or "none").lower()
            url = (r.get("url") or "").strip()
            name = (r.get("official_name") or "").strip()

            e["verify"] = conf
            e["verify_source"] = f.name
            if r.get("evidence"):
                e["evidence"] = r["evidence"]

            if url and conf in ("high", "medium", "low"):
                if e.get("url") and e["url"] != url:
                    e["prev_url"] = e["url"]
                e["url"] = url
                e["conf"] = conf
                e["needs_verify"] = conf == "low"
                if name:
                    e["official_name"] = name
                stats[conf] += 1
            else:
                e["unresolved"] = True
                e["conf"] = "none"
                stats["none"] += 1

    # 汇总
    with_url = [e for e in data["expos"] if e.get("url")]
    print("合并 %d 个文件" % len(merged_files))
    print("  采用 high=%d medium=%d low=%d ｜ 仍未确定=%d" % (
        stats["high"], stats["medium"], stats["low"], stats["none"]))
    if stats["unknown_id"]:
        print("  ⚠ 未知 id: %s" % stats["unknown_id"])
    print("  名单含 URL: %d / %d" % (len(with_url), len(data["expos"])))

    data["version"] = "v2"
    data["note"] = (
        data["note"]
        + " v2: 经 WebSearch 查证后合并，verify 字段记录证据强度；"
        "prev_url 为被推翻的旧猜测，official_name 为查证到的真实全称。"
    )
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("→ %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
