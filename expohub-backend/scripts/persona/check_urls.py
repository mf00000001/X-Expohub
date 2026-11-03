"""
批次 0：核查 100 个候选展会的官网 URL 是否真实可抓。

只做三件事，不加任何采集逻辑：
  1. URL 能不能打开（跟随跳转，判 2xx）
  2. 打开的是不是这个展会（用标题/正文关键词匹配，防域名被抢注跳走）
  3. robots.txt 允不允许抓（沿用 expo_scraper 的规则：取不到即视为不允许）

输出逐条结果 + 汇总，JSON 与人类可读两个版本。
不联网改数据、不落库、不写主库。

用法：
    python scripts/persona/check_urls.py                # 跑全部
    python scripts/persona/check_urls.py --layer trunk   # 只跑某一层
    python scripts/persona/check_urls.py --limit 10      # 抽前 N 条
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / "data" / "expo_candidates_v1.json"
OUT_DIR = ROOT / "data" / "batch0"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = 12
MAX_BYTES = 200_000

# 绕开系统代理：这台机器常驻 127.0.0.1:7891，国内展会站走代理会被接走并回假错误
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
# 核查阶段不验证证书：大量国内展会站缺中间证书，浏览器能正常打开但我们这里会报
# CERTIFICATE_VERIFY_FAILED，从而把"能访问"误判成"站点已死"。这里只读公开页、不提交任何数据。
_OPENER_INSECURE = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
)

_CN = re.compile(r"[\u4e00-\u9fff]")


def _decode(raw: bytes, hint: str | None) -> str:
    """解码。

    不能用'解出汉字最多的编码'当判据：UTF-8 的中文用 GBK 也能解出一堆汉字（乱码
    但仍是汉字），计数差不出来。正确做法是利用 UTF-8 是自校验编码这一点——
    能严格解码成功就基本确定是 UTF-8，失败才是 GBK/GB18030。
    """
    if hint:
        h = hint.lower()
        if h not in ("utf-8", "utf8"):
            try:
                return raw.decode(h)
            except (LookupError, UnicodeDecodeError):
                pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        for c in ("gb18030", "gbk", "big5"):
            try:
                return raw.decode(c)
            except (LookupError, UnicodeDecodeError):
                continue
    return raw.decode("utf-8", "ignore")


def _get(url: str, timeout: int = TIMEOUT) -> tuple[int, str, str, str, str]:
    """返回 (status, final_url, title, body_head, ssl_note)。失败抛异常。"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            # 很多站点默认 gzip；urllib 不会自动解，必须显式声明并自行解压，
            # 否则读到的是压缩字节，标题解析为空 → 被判成"不像这家展"（假阴性）
            "Accept-Encoding": "gzip, deflate",
        },
    )
    ssl_note = ""
    try:
        resp_cm = _OPENER.open(req, timeout=timeout)
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), ssl.SSLError):
            ssl_note = "证书/握手异常，已降级重试"
            resp_cm = _OPENER_INSECURE.open(req, timeout=timeout)
        else:
            raise
    with resp_cm as resp:
        raw = resp.read(MAX_BYTES * 10)
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc:
            try:
                raw = gzip.decompress(raw)
            except Exception:
                raw = b""
        elif "deflate" in enc:
            try:
                raw = zlib.decompress(raw)
            except Exception:
                try:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                except Exception:
                    raw = b""
        raw = raw[:MAX_BYTES]

        ctype = resp.headers.get("Content-Type", "")
        hint = None
        m = re.search(r"charset=([\w-]+)", ctype, re.I)
        if m:
            hint = m.group(1)
        else:
            m2 = re.search(rb"charset=[\"']?([\w-]+)", raw[:3000], re.I)
            if m2:
                hint = m2.group(1).decode("ascii", "ignore")
        html = _decode(raw, hint)
        title = ""
        mt = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        if mt:
            title = re.sub(r"\s+", " ", mt.group(1)).strip()[:200]
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)[:4000]
        return resp.status, resp.geturl(), title, text, ssl_note


def _robots(host_root: str) -> tuple[str, list[str]]:
    """返回 (状态, 命中的 Disallow 规则)。状态：allow / deny / missing / error。"""
    url = host_root.rstrip("/") + "/robots.txt"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with _OPENER.open(req, timeout=8) as resp:
            body = resp.read(64_000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "deny", ["robots 返回 %d" % e.code]
        return "missing", ["无 robots.txt(%d) → 按规则视为不允许" % e.code]
    except Exception as e:  # 超时 / DNS / SSL
        return "error", ["robots 取不到(%s) → 按规则视为不允许" % type(e).__name__]

    # 极简解析：只看 User-agent: * 段里的 Disallow: /
    blocks = re.split(r"(?im)^\s*user-agent\s*:", body)
    for b in blocks[1:]:
        head, _, rest = b.partition("\n")
        if head.strip() == "*":
            disallows = re.findall(r"(?im)^\s*disallow\s*:\s*(\S*)", rest)
            hard = [d for d in disallows if d.strip() in ("/",)]
            if hard:
                return "deny", ["Disallow: /"]
            return "allow", disallows[:5]
    return "allow", []


def check_one(item: dict) -> dict:
    out = {
        "id": item["id"],
        "layer": item["layer"],
        "category": item["category"],
        "name": item["name"],
        "short": item.get("short", ""),
        "city": item.get("city", ""),
        "url": item.get("url", ""),
        "conf": item.get("conf", ""),
    }
    if not item.get("url"):
        out.update(result="no_url", detail="尚未确定官网", robots="n/a")
        return out

    t0 = time.time()
    try:
        status, final, title, text, ssl_note = _get(item["url"])
        out["http"] = status
        out["final_url"] = final
        out["title"] = title
        out["elapsed"] = round(time.time() - t0, 2)
        if ssl_note:
            out["ssl_note"] = ssl_note

        hay = (title + " " + text).lower()
        hits = [k for k in item.get("kw", []) if k.lower() in hay]
        out["kw_hits"] = hits

        # 域名是否还指向自己：这比关键词更能反映"有没有被抢注/劫持/跳走"
        def _host(u: str) -> str:
            h = urllib.parse.urlsplit(u).netloc.lower()
            return h[4:] if h.startswith("www.") else h

        h_in, h_out = _host(item["url"]), _host(final)
        host_same = h_out == h_in or h_out.endswith("." + h_in) or h_in.endswith("." + h_out)
        out["host_same"] = host_same

        if hits:
            out["result"] = "ok"
            out["detail"] = "命中 " + "、".join(hits[:3])
        elif host_same:
            # 域名没变、就是打不开内容匹配：多半是前端渲染（SPA），标题为空
            out["result"] = "ok_by_host"
            out["detail"] = "域名未变，但正文未匹配" + ("（标题为空，疑为JS渲染）" if not title else "")
        else:
            out["result"] = "ok_no_kw"
            out["detail"] = "跳转到 %s，未见展会关键词" % h_out
    except urllib.error.HTTPError as e:
        out.update(
            result="http_err",
            http=e.code,
            detail="HTTP %d" % e.code,
            elapsed=round(time.time() - t0, 2),
        )
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        out.update(result="net_err", detail="%s: %s" % (type(reason).__name__, str(reason)[:80]),
                   elapsed=round(time.time() - t0, 2))
    except (socket.timeout, ssl.SSLError, TimeoutError) as e:
        out.update(result="net_err", detail="%s" % type(e).__name__, elapsed=round(time.time() - t0, 2))
    except Exception as e:
        out.update(result="net_err", detail="%s: %s" % (type(e).__name__, str(e)[:80]),
                   elapsed=round(time.time() - t0, 2))

    # robots 只对能解析出主机的条目查
    try:
        from urllib.parse import urlsplit

        sp = urlsplit(out.get("final_url") or item["url"])
        root = "%s://%s" % (sp.scheme, sp.netloc)
        st, rules = _robots(root)
        out["robots"] = st
        out["robots_rules"] = rules
    except Exception as e:
        out["robots"] = "error"
        out["robots_rules"] = [str(e)[:60]]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=["trunk", "cross", "boundary"], default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--input", default=str(CANDIDATES), help="候选名单 JSON 路径")
    args = ap.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    items = data["expos"]
    if args.layer:
        items = [x for x in items if x["layer"] == args.layer]
    if args.limit:
        items = items[: args.limit]

    print("待核查 %d 条，并发 %d" % (len(items), args.workers))
    results: list[dict] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(check_one, it): it for it in items}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            flag = {"ok": "OK ", "ok_no_kw": "KW?", "no_url": "-- ", "http_err": "HTTP",
                    "net_err": "NET"}.get(r["result"], "???")
            print("  [%3d/%3d] %s %-22s %-30s %s" % (
                i, len(items), flag, r["id"], r["name"][:28], r.get("detail", "")[:46]))

    order = {it["id"]: i for i, it in enumerate(items)}
    results.sort(key=lambda x: order[x["id"]])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "url_check.json").write_text(
        json.dumps({"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "total": len(results), "results": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 汇总
    from collections import Counter

    cnt = Counter(r["result"] for r in results)
    rob = Counter(r.get("robots", "n/a") for r in results
                  if r["result"] in ("ok", "ok_by_host", "ok_no_kw"))

    # 三态可用性：把 http 结果与 robots 合成一个能直接指导决策的结论
    def verdict(r: dict) -> str:
        if r["result"] == "no_url":
            return "no_url"          # 官网未知，采集无从谈起
        if r["result"] in ("http_err", "net_err"):
            return "dead"            # 打不开
        if r["result"] == "ok_no_kw":
            return "unverified"      # 跳到了别的域且不像这家展
        rb = r.get("robots")
        if rb == "deny":
            return "blocked"         # 明确禁止
        return "usable" if rb == "allow" else "usable_std_only"

    for r in results:
        r["verdict"] = verdict(r)
    vcnt = Counter(r["verdict"] for r in results)
    render = [r for r in results if r.get("result") == "ok_by_host"]

    print("\n" + "=" * 74)
    print("核查完成，用时 %.1f 秒" % (time.time() - t0))
    print("=" * 74)
    print("总条数        %d" % len(results))
    for k, label in [("ok", "命中关键词，确认是这家展"), ("ok_by_host", "域名未变但正文没匹配到"),
                     ("ok_no_kw", "跳转到别处且没匹配到"), ("http_err", "HTTP 错误"),
                     ("net_err", "网络/DNS/超时"), ("no_url", "官网尚未确定")]:
        if cnt.get(k):
            print("%-20s %3d  (%.0f%%)" % (label, cnt[k], 100 * cnt[k] / len(results)))
    print()
    print("可访问条目的 robots：allow=%d deny=%d missing=%d error=%d" % (
        rob.get("allow", 0), rob.get("deny", 0), rob.get("missing", 0), rob.get("error", 0)))

    n = len(results)
    print()
    print("-" * 74)
    print("可用性三态（这才是能否采集的结论）")
    print("-" * 74)
    for k, label in [("usable", "可抓：能打开 + 确认是这家展 + robots 允许"),
                     ("usable_std_only", "准可抓：无 robots.txt（标准允许 / 现规则不允许）"),
                     ("blocked", "被 robots 禁止"),
                     ("unverified", "存疑：能打开但不像这家展"),
                     ("dead", "打不开：HTTP 错误 / DNS / 超时"),
                     ("no_url", "官网未知")]:
        if vcnt.get(k):
            print("  %-6s %3d  (%.0f%%)  %s" % (k, vcnt[k], 100 * vcnt[k] / n, label))
    print()
    print("  按现规则  = %d 条 (%.0f%%)" % (vcnt.get("usable", 0), 100 * vcnt.get("usable", 0) / n))
    print("  按RFC9309 = %d 条 (%.0f%%)" % (
        vcnt.get("usable", 0) + vcnt.get("usable_std_only", 0),
        100 * (vcnt.get("usable", 0) + vcnt.get("usable_std_only", 0)) / n))
    if render:
        print("  其中 %d 条域名未跳转但正文抓不到内容（前端渲染，需 headless 才能采）" % len(render))
    print("→ 落盘: %s" % (OUT_DIR / "url_check.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
