"""
批次 0 收尾：补关键词、标重复、标可疑，产出最终统计。

三件事：
  1. 补 kw：有些页面内容明明对得上，只是关键词表里少了那个词（如广交会页面写"广交会"
     但 kw 里只有"消费品"），造成假阴性
  2. 标 duplicate_of：100 条里确有同一展被两个 id 收录，标本量时必须剔重
  3. 标 suspicious：能打开但内容指向别的展（域名被复用/跳转到同集团其他业务）

输出 data/expo_candidates_final.json 和 data/batch0/summary.json
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "expo_candidates_v2.json"
CHECK = ROOT / "data" / "batch0" / "url_check.json"
OUT = ROOT / "data" / "expo_candidates_final.json"
SUM = ROOT / "data" / "batch0" / "summary.json"

# 页面已确认对得上，只是关键词表缺词
KW_PATCH = {
    "b-general-consumer": ["广交会", "Canton"],
    "b-tea-drink": ["茶博", "teaexpo"],
    "china-edu-expo": ["CEE", "Education"],
    "jinjiang-shoes": ["Footwear", "cn-jif", "JIF"],
    "itma-asia": ["纺织机械"],
    "b-textile-machinery": ["纺织机械"],
    "china-logistics": ["Logistic", "物博"],
    "b-camping": ["露营", "户外"],
}

# 同一展的重复收录：dup → 保留哪个
DUP_OF = {
    "b-hardware-industrial": "cihs",
    "b-machine-tool": "ccmt",
    "b-houseware": "china-daily-goods",
    "b-textile-machinery": "itma-asia",
    "b-medical-device": "cmef",
    "b-general-consumer": "canton-fair",
}

# 能打开但内容不是这家展
SUSPICIOUS = {
    "b-camping": "hweexpo.cn 实际是 SVE 上海国际休闲运动车展，不是户外露营展",
    "furniture-china": "furniture-china.cn 现跳转 jiagle.com（华夏家博会，B2C 消费展），非中国国际家具展",
}


def host(u: str) -> str:
    h = urlsplit(u).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    chk = {r["id"]: r for r in json.loads(CHECK.read_text(encoding="utf-8"))["results"]}

    for e in data["expos"]:
        eid = e["id"]
        if eid in KW_PATCH:
            kw = list(dict.fromkeys((e.get("kw") or []) + KW_PATCH[eid]))
            e["kw"] = kw
        if eid in DUP_OF:
            e["duplicate_of"] = DUP_OF[eid]
        if eid in SUSPICIOUS:
            e["suspicious"] = SUSPICIOUS[eid]
        # 把核查结论一并挂上，后面写报告直接读
        c = chk.get(eid, {})
        e["check"] = {
            "result": c.get("result"),
            "verdict": c.get("verdict"),
            "http": c.get("http"),
            "robots": c.get("robots"),
            "title": (c.get("title") or "")[:80],
        }

    # 重新判定（考虑 kw 补充与可疑标记）
    def final_status(e: dict) -> str:
        if e.get("suspicious"):
            return "suspicious"
        if e.get("duplicate_of"):
            return "duplicate"
        c = e.get("check") or {}
        res, rb, url = c.get("result"), c.get("robots"), e.get("url")
        if not url:
            return "no_url"
        if res in ("http_err", "net_err"):
            # 403 是反爬不是不存在；SSL 握手失败同理
            return "blocked_by_site" if (c.get("http") == 403 or "SSL" in str(c.get("detail", ""))) else "dead"
        if res == "ok_no_kw":
            return "suspicious"
        if rb == "deny":
            return "robots_denied"
        if c.get("result") == "ok_by_host":
            return "needs_render"          # 域名对、内容抓不到
        return "crawlable" if rb == "allow" else "crawlable_if_std"

    for e in data["expos"]:
        e["status"] = final_status(e)

    cnt = collections.Counter(e["status"] for e in data["expos"])

    # 按层级、品类交叉
    by_layer = collections.defaultdict(collections.Counter)
    for e in data["expos"]:
        by_layer[e["layer"]][e["status"]] += 1
    by_cat = collections.defaultdict(lambda: [0, 0])
    for e in data["expos"]:
        by_cat[e["category"]][0] += 1
        if e["status"] in ("crawlable", "crawlable_if_std", "needs_render"):
            by_cat[e["category"]][1] += 1

    n = len(data["expos"])
    out = {
        "total": n,
        "unique": n - len(DUP_OF),
        "status": dict(cnt),
        "by_layer": {k: dict(v) for k, v in by_layer.items()},
        "by_category": {k: {"total": v[0], "usable": v[1]} for k, v in sorted(by_cat.items())},
        "note": {
            "crawlable": "能打开 + 内容是这家展 + robots 允许：纯 HTTP 直接可采",
            "crawlable_if_std": "同上，但站点无 robots.txt。RFC 9309 视为允许，现 scraper 视为不允许",
            "needs_render": "域名未跳转但正文为空：前端渲染，需 headless 浏览器",
            "blocked_by_site": "站点存在但拒绝（403/SSL 握手），只能人工录入",
            "duplicate": "与另一 id 是同一展会，统计时要剔除",
            "suspicious": "能打开但内容不是这家展，URL 不可用",
        },
    }

    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    SUM.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 66)
    print("批次 0 最终统计")
    print("=" * 66)
    print("总条目 %d ｜ 去重后唯一展会 %d" % (n, out["unique"]))
    print()
    for k in ("crawlable", "crawlable_if_std", "needs_render", "blocked_by_site",
              "robots_denied", "dead", "suspicious", "duplicate", "no_url"):
        if cnt.get(k):
            print("  %-18s %3d" % (k, cnt[k]))
    print()
    print("按层：")
    for layer in ("trunk", "cross", "boundary"):
        d = by_layer.get(layer, {})
        tot = sum(d.values())
        ok = d.get("crawlable", 0) + d.get("crawlable_if_std", 0) + d.get("needs_render", 0)
        print("  %-9s 共 %2d，可用 %2d" % (layer, tot, ok))
    print()
    print("按品类（可用/总数）：")
    for cat, v in out["by_category"].items():
        print("  %-14s %2d/%2d" % (cat, v["usable"], v["total"]))
    print()
    print("→ %s" % OUT)
    print("→ %s" % SUM)
    return 0


if __name__ == "__main__":
    sys.exit(main())
