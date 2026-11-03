"""
用无头浏览器补采 17 个纯前端渲染站点。

为什么必须有这一步：19 个站的 HTML 里只有 <div id="app"></div> 和一堆 JS，
静态抓取拿到的正文不足 1200 字（最短 106 字），LLM 对这类输入只能返回全 null——
它做得对，没内容就是没内容。**这些站里包含广交会、进博会、服贸会、工博会**，
按展会重要性加权，这个缺口远大于 19/94。

设计要点：
  · **不下载 Playwright 自带浏览器**，直接复用本机已装的 Chrome/Edge
    （`channel="chrome"`）。省 150MB 下载，也避免代理导致的下载失败。
  · 渲染结果写到 `data/batch1/rendered/`，**不覆盖** `raw/`。
    两条来源必须分开存：静态页说没说、说了什么，是判断"该不该上浏览器"的依据，
    覆盖掉就再也回不去了。
  · 逐站记录渲染后的正文字数、耗时、失败原因。渲染失败不等于站点有问题，
    超时/反爬/验证码都要能区分，否则会得出"这些站都抓不到"的错误结论。

用法：
    python scripts/persona/render_spa.py                 # 全部
    python scripts/persona/render_spa.py --ids ciie,ciif
    python scripts/persona/render_spa.py --headed        # 有头，调试用
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "batch1" / "raw"
RENDERED = ROOT / "data" / "batch1" / "rendered"
OUT = ROOT / "data" / "batch1" / "render_log.json"

THRESHOLD = 1200          # 静态正文短于此值才需要渲染
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 首页常是门户（新闻轮播 + 导航），展期/展馆/主办方在"关于/参展"页。
# 渲染完首页再去 1~2 个子页，比在首页里翻新闻划算得多。
SUB_HINTS = ("关于", "简介", "概况", "介绍", "参展", "展位", "报名",
             "about", "overview", "exhibit", "fair")
SUB_BLOCK = ("login", "register", "news", "新闻", "download", "下载",
             "video", "member", "cart", "javascript:", ".pdf")


def pick_subpages(page, main_url: str, limit: int = 2) -> list[str]:
    """从**已渲染**的页面里取同域链接。链接文字优先于 URL 路径。

    很多站的路径是 /contents/101/14166.html，路径里没有 about/exhibit，
    只有 <a> 的文字能看出这是什么页。
    """
    try:
        links = page.evaluate(
            "() => Array.from(document.querySelectorAll('a[href]'))"
            ".map(a => ({href: a.href, text: (a.textContent || '').trim().slice(0, 30)}))")
    except Exception:
        return []
    from urllib.parse import urlsplit
    host = urlsplit(main_url).netloc
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for a in links or []:
        href, text = (a.get("href") or ""), (a.get("text") or "")
        if not href.startswith("http") or urlsplit(href).netloc != host:
            continue
        u = href.split("#")[0]
        if u.rstrip("/") == main_url.rstrip("/") or u in seen:
            continue
        low = u.lower()
        if any(b in low for b in SUB_BLOCK):
            continue
        low_t = text.lower()
        score = 0
        if any(h in low_t for h in SUB_HINTS):
            score += 10
        if any(h in low for h in ("about", "exhibit", "fair-info", "overview")):
            score += 4
        if score:
            seen.add(u)
            scored.append((score, u))
    scored.sort(key=lambda x: -x[0])
    return [u for _, u in scored[:limit]]


def render(page, url: str) -> tuple[str, str]:
    """返回 (text, status)。status 用于区分"渲染成功但没内容"和"根本没加载出来"。

    「Navigation is interrupted by another navigation」这类报错必须吞掉：
    很多站首页会立刻 JS 跳转到 /zh/ 或 /home，Playwright 认为第一次导航被中断而抛异常，
    但页面其实已经正常加载了。当成失败处理会把能采的站误判成采不到。
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=35000)
    except Exception as ex:
        if "interrupted by another navigation" in str(ex):
            page.wait_for_timeout(1200)          # 等二次跳转落定
        else:
            # 退回最宽松的等待条件再试一次：只要求服务器开始响应
            page.goto(url, wait_until="commit", timeout=35000)
            page.wait_for_timeout(2000)

    # SPA 的首屏内容通常在 XHR 回来后才有。networkidle 有时永远等不到（长轮询/心跳），
    # 所以给它一个上限，超时不算失败，接着取文本。
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    # 懒加载：先滚到底再回顶，很多站的展期/展馆在首屏以下
    try:
        page.evaluate("""() => {
            const h = document.body.scrollHeight;
            window.scrollTo(0, h);
            setTimeout(() => window.scrollTo(0, 0), 300);
        }""")
    except Exception:
        pass
    page.wait_for_timeout(1500)

    text = page.evaluate("() => document.body ? document.body.innerText : ''")
    text = (text or "").strip()
    if len(text) < THRESHOLD:
        # 有些站把内容放在 iframe 或 shadow DOM，innerText 取不到，退回 textContent
        alt = page.evaluate("() => document.body ? document.body.textContent : ''") or ""
        alt = " ".join(alt.split())
        if len(alt) > len(text):
            text = alt
    return text, "ok" if text else "empty"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--force", action="store_true", help="已有渲染结果的也重跑")
    ap.add_argument("--channel", default="chrome", choices=["chrome", "msedge"])
    ap.add_argument("--subpages", type=int, default=2,
                    help="额外渲染几个'关于/参展'子页（0 = 只渲染首页）")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    cand = json.loads((ROOT / "data" / "expo_candidates_final.json").read_text(encoding="utf-8"))
    short = {p.stem for p in RAW.glob("*.txt") if len(p.read_text(encoding="utf-8")) < THRESHOLD}
    if args.ids:
        short &= {s.strip() for s in args.ids.split(",")}
    targets = [e for e in cand["expos"] if not e.get("duplicate_of") and e["id"] in short]
    RENDERED.mkdir(parents=True, exist_ok=True)

    if not args.force:
        targets = [e for e in targets
                   if not (RENDERED / f"{e['id']}.txt").exists()]

    print("渲染 %d 个站点（浏览器 = 本机 %s，不下载）\n" % (len(targets), args.channel))
    log = []
    t0 = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel, headless=not args.headed)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                                  locale="zh-CN")
        # 图片/字体/媒体一律不加载：只要文字，拦掉它们能把单站耗时压掉一半以上
        ctx.route("**/*", lambda route: route.abort()
                  if route.request.resource_type in ("image", "font", "media")
                  else route.continue_())

        for i, e in enumerate(targets, 1):
            # 每站一个独立 page：上一次被中断的导航会污染同一个 page 的状态，
            # 表现为后面所有站都报 "interrupted"，明明它们本身没问题
            page = ctx.new_page()
            rec = {"id": e["id"], "url": e.get("url")}
            ts = time.time()
            try:
                text, status = render(page, e["url"])
                subs: list[str] = []
                if text and args.subpages > 0:
                    for sub in pick_subpages(page, e["url"], args.subpages):
                        sp = ctx.new_page()
                        try:
                            st2, _ = render(sp, sub)
                            if st2 and len(st2) > 200:
                                subs.append((sub, st2))
                        except Exception:
                            pass
                        finally:
                            try:
                                sp.close()
                            except Exception:
                                pass
                rec.update({"status": status, "chars": len(text),
                            "subpages": [s for s, _ in subs],
                            "sub_chars": sum(len(t) for _, t in subs)})
                if text:
                    # 前面补上来源标记，与 raw/ 的格式对齐，LLM 那边不用改
                    merged = text + "".join(
                        "\n\n===== 子页 %s =====\n%s" % (u, t) for u, t in subs)
                    (RENDERED / f"{e['id']}.txt").write_text(
                        "URL: %s\nSOURCE: rendered(%s)\nRENDERED_AT: %s\nSUBPAGES: %d\n%s\n%s" % (
                            e["url"], args.channel, datetime.now().strftime("%Y-%m-%d %H:%M"),
                            len(subs), "-" * 60, merged), encoding="utf-8")
            except Exception as ex:
                rec.update({"status": "error", "chars": 0,
                            "error": f"{type(ex).__name__}: {str(ex)[:80]}"})
            finally:
                try:
                    page.close()
                except Exception:
                    pass
            rec["seconds"] = round(time.time() - ts, 1)
            log.append(rec)
            print("  [%2d/%2d] %-18s %-6s %5d 字  %4.1fs" % (
                i, len(targets), e["id"], rec["status"], rec["chars"], rec["seconds"]))

        browser.close()

    ok = [r for r in log if r["status"] == "ok"]
    print("\n成功 %d / %d ｜ 用时 %.0f 秒" % (len(ok), len(log), time.time() - t0))
    if ok:
        print("平均正文 %.0f 字（渲染前这些站不足 %d 字）" % (
            sum(r["chars"] for r in ok) / len(ok), THRESHOLD))
    bad = [r for r in log if r["status"] != "ok"]
    if bad:
        print("\n未成功：")
        for r in bad:
            print("  %-18s %s %s" % (r["id"], r["status"], r.get("error", "")))

    prev = []
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8")).get("records", [])
        except json.JSONDecodeError:
            prev = []
    keep = {r["id"]: r for r in prev}
    keep.update({r["id"]: r for r in log})
    OUT.write_text(json.dumps({"rendered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                               "records": list(keep.values())}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("→ %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
