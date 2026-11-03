"""
诊断：正文过短的站点到底是"没数据"还是"数据在别处"。

上无头浏览器是最后手段（装环境、单站 3~8 秒、要处理反爬）。在花这个代价之前，
先判断每个站属于哪一类——不同类的解法完全不同，混在一起处理会白花很多时间：

  ssr_embedded   HTML 里内嵌了完整数据（__NUXT__ / __NEXT_DATA__ / __INITIAL_STATE__）
                 → 直接解 JSON，不需要浏览器，最便宜
  json_ld        有 schema.org Event 结构化数据
                 → 直接读，我们的 extract_jsonld_event 已经支持
  api_hint        HTML/JS 里能看出后端 API 地址
                 → 试着直接打接口，往往返回纯 JSON
  shell_only     只有一个空 div + 一堆 JS 文件，什么都没有
                 → 只能上浏览器，或者放弃

用法：
    python scripts/persona/probe_spa.py
    python scripts/persona/probe_spa.py --ids canton-fair,ciie
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "batch1" / "raw"
OUT = ROOT / "data" / "batch1" / "spa_probe.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_skeleton import fetch, visible_text  # noqa: E402

THRESHOLD = 1200

MARKERS = {
    "nuxt": re.compile(r"window\.__NUXT__\s*=", re.I),
    "next": re.compile(r'id="__NEXT_DATA__"', re.I),
    "initial_state": re.compile(r"window\.__INITIAL_STATE__\s*=", re.I),
    "preloaded": re.compile(r"window\.__PRELOADED_STATE__\s*=", re.I),
    "jsdata": re.compile(r'<script[^>]+type="application/(?:ld\+)?json"[^>]*>', re.I),
}

# 从 JS 里捞 API 基址：绝对路径最可靠，相对路径误报太多就不捞了
API_PAT = re.compile(r"""["'](https?://[a-z0-9.\-]+(?:/[a-zA-Z0-9_\-./]*)?/(?:api|json|interface|service)[a-zA-Z0-9_\-./]*)["']""", re.I)
BASE_ABS = re.compile(r"""["'](https?://[a-z0-9.\-]+\.(?:com|cn|org|net)(?::\d+)?)["']""", re.I)


def extra_json_blocks(html: str) -> int:
    """内嵌 JSON 的总字符数。大于 2000 基本说明数据在里面。"""
    total = 0
    for m in re.finditer(r'<script[^>]+type="application/(?:ld\+)?json"[^>]*>(.*?)</script>',
                         html, re.S | re.I):
        total += len(m.group(1))
    for pat in (r"window\.__NUXT__\s*=\s*(\{.*?\});?\s*</script>",
                r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*</script>"):
        for m in re.finditer(pat, html, re.S):
            total += len(m.group(1))
    return total


def probe(e: dict) -> dict:
    rec = {"id": e["id"], "url": e.get("url"), "kind": "unknown", "notes": []}
    if not e.get("url"):
        rec["kind"] = "no_url"
        return rec
    try:
        status, final, html = fetch(e["url"])
    except Exception as ex:
        rec["kind"] = "fetch_error"
        rec["notes"].append(f"{type(ex).__name__}: {str(ex)[:60]}")
        return rec

    text = visible_text(html)
    rec.update({
        "http": status, "html_chars": len(html), "text_chars": len(text.strip()),
        "scripts": len(re.findall(r"<script\b", html, re.I)),
    })

    hits = [name for name, pat in MARKERS.items() if pat.search(html)]
    rec["markers"] = hits
    rec["embedded_json_chars"] = extra_json_blocks(html)

    if re.search(r'<script[^>]+type="application/ld\+json"', html, re.I):
        rec["kind"] = "json_ld"
    elif rec["embedded_json_chars"] > 2000:
        rec["kind"] = "ssr_embedded"
    else:
        # 退一步：找 API 线索
        apis = list(dict.fromkeys(API_PAT.findall(html)))[:5]
        bases = list(dict.fromkeys(BASE_ABS.findall(html)))[:5]
        if apis:
            rec["kind"] = "api_hint"
            rec["apis"] = apis
        elif bases and not hits:
            rec["kind"] = "shell_only"
            rec["other_hosts"] = bases
        else:
            rec["kind"] = "shell_only"

    rec["external_js"] = list(dict.fromkeys(
        re.findall(r'<script[^>]+src=["\']([^"\']+\.js[^"\']*)["\']', html, re.I)))[:6]
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    args = ap.parse_args()

    cand = json.loads((ROOT / "data" / "expo_candidates_final.json").read_text(encoding="utf-8"))
    short = {p.stem for p in RAW.glob("*.txt")
             if len(p.read_text(encoding="utf-8")) < THRESHOLD}
    expos = [e for e in cand["expos"] if not e.get("duplicate_of") and e["id"] in short]
    if args.ids:
        want = {s.strip() for s in args.ids.split(",")}
        expos = [e for e in expos if e["id"] in want]

    print("诊断 %d 个正文过短的站点（阈值 %d 字）\n" % (len(expos), THRESHOLD))
    t0 = datetime.now()
    recs = []
    for i, e in enumerate(expos, 1):
        r = probe(e)
        recs.append(r)
        print("  [%2d/%2d] %-18s %-14s html %6d · text %5d · json %6d  %s" % (
            i, len(expos), r["id"], r["kind"], r.get("html_chars", 0),
            r.get("text_chars", 0), r.get("embedded_json_chars", 0),
            ",".join(r.get("markers", []))))

    by = {}
    for r in recs:
        by[r["kind"]] = by.get(r["kind"], 0) + 1
    print("\n分类：" + " ｜ ".join("%s=%d" % (k, v) for k, v in sorted(by.items(), key=lambda x: -x[1])))
    print("用时 %.0f 秒" % (datetime.now() - t0).total_seconds())

    OUT.write_text(json.dumps({"probed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                               "records": recs}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("→ %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
