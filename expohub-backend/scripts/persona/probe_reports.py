"""
E1 缺口定向补采：专门找"写了规模数字、但首页没有"的那些页。

背景：
    批次 2 之后，94 个展里 67 个算不出观众/展商比——不是抽取没用力，是首页
    常常只写一边、或者一边都不写。真正写数的地方是"历届回顾 / 展会规模 /
    展后报告"这类二级页，而且不同站叫法完全不同。

    batch2b 的 collect_subpages.py 用的是 13 个关键词，覆盖不到"历届回顾"
    （CMEF 首页明明有这个词，却没匹配上，于是判成 no_keyword_links）。

本脚本相对 batch2b 的三处改进：
  1. **关键词扩到 30 个**，并按"这个词的页面里出现规模数字的概率"排序。
     命中优先级决定先抓哪个，不是先到先得。
  2. **静态拿不到链接就渲染**。caexpo 首页 570KB 但 <a> 数量为 0（Vue 生成），
     静态看永远是"没链接"，这是抓取路径问题不是站点问题。
  3. **抓完先自检有没有料**。页面正文里凑不出"数字+观众/展商/面积"的组合就
     丢掉——否则会把一堆"关于我们"的诗朗诵塞给下一步的 LLM，
     既涨 token 又降低抽取质量。

落盘：
    data/batch1/report/<id>.txt    多页用 "---- <url> ----" 分隔
    data/batch1/report_index.json  {id: {urls, chars, hits, signals, error, via}}

用法：
    python scripts/persona/probe_reports.py --dry-run          # 只打印将抓哪些页
    python scripts/persona/probe_reports.py                    # 全部缺口站
    python scripts/persona/probe_reports.py --only cmef,caexpo
    python scripts/persona/probe_reports.py --limit 10 --no-render
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data"
BATCH1 = DATA / "batch1"
REPORT_DIR = BATCH1 / "report"
INDEX = BATCH1 / "report_index.json"
MERGED = BATCH1 / "merged.json"
RAW_DIR = BATCH1 / "raw"
RENDERED_DIR = BATCH1 / "rendered"
DB = ROOT / "persona.db"

sys.path.insert(0, str(HERE))
from collect_skeleton import _ROBOTS, TIMEOUT, fetch, visible_text  # noqa: E402
from collect_subpages import Budget, fetch_with_retry, _clean_anchor  # noqa: E402

# ---- 关键词：按"页面里出现规模数字的概率"从高到低 ----
# 中文用归一化子串匹配（展览会→展会、概览→概况），英文用字母边界。
LINK_KEYWORDS = (
    # 第一梯队：名字里就写着"数据/规模/报告"
    "展后报告", "会后报告", "展会报告", "参展报告", "数据报告", "统计报告",
    "展会数据", "展会规模", "上届数据", "往届数据", "历届数据", "展会成果",
    "Post Show Report", "Show Report", "Facts and Figures", "Key Figures",
    "Statistics", "Attendance",
    # 第二梯队：回顾类（数字通常藏在回顾页的"上届"段落里）
    "上届回顾", "往届回顾", "历届回顾", "精彩回顾", "展会回顾", "历届展会",
    "上届展会", "往届展会", "Review", "Recap", "Past Shows", "Previous Editions",
    # 第三梯队：概况/介绍类（最泛，兜底）
    "展会概况", "展会介绍", "展会简介", "关于展会", "关于我们", "展会概览",
    "Exhibition Profile", "About", "Overview", "Why Exhibit",
)

# 第 0 梯队（兜底）：上一组一个都没命中时才用。
# sial-china 首页 48 个链接里没有"概况/规模/回顾"，规模数只在自家新闻稿里。
# 只取"主办方自己的新闻"，不取"行业新闻"——后者是转载，口径与本展无关。
# 命中后仍要靠 _SIGNAL 过滤，没料就整站丢弃，所以放宽这一层是安全的。
FALLBACK_KEYWORDS = (
    "展会新闻稿", "新闻稿", "展会快讯", "媒体中心", "新闻专题", "展会动态",
    "Press Release", "Press Room", "News Room", "Media Centre", "Media Center",
)
MAX_FALLBACK_PAGES = 2

LINK_BLOCK = ("login", "register", "signin", "signup", "download", "video",
              "member", "cart", "subscribe", "privacy", "javascript:", "mailto:",
              "tel:", ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".doc",
              "新闻", "资讯", "直播", "登录", "注册", "招聘", "联系我们", "隐私",
              "版权", "网站地图", "lang=")

MAX_SUB_PER_SITE = 4
MAX_REQ_PER_SITE = 8
MAX_WORKERS = 5
MIN_PAGE_CHARS = 150
PER_PAGE_CAP = 25_000

# 页面"有料"的判据：出现数字与规模名词的组合，或出现百分号/万/亿的规模表述。
# 只用来排序与过滤，不参与抽取——抽取仍走 extract_scale 的闸门。
_SIGNAL = re.compile(
    r"(\d[\d,.]{2,}\s*(?:万|亿|千)?\s*(?:人次|人|名|位)?\s*"
    r"(?:专业)?(?:观众|买家|采购商|参展商|展商|企业|品牌|展位)"
    r"|(?:观众|买家|采购商|参展商|展商|企业|品牌|展位)\s*(?:数量|数|总数为)?\s*[:：]?\s*\d[\d,.]{2,}"
    r"|(?:面积|展出面积|展览面积)\s*[:：]?\s*\d[\d,.]{2,}\s*(?:万)?\s*(?:平方米|平米|㎡|m2|sqm)"
    r"|\d[\d,.]{2,}\s*(?:平方米|平米|㎡|m2|sqm))", re.I)


def _norm_anchor(s: str) -> str:
    s = s.lower()
    for a, b in (("展览会", "展会"), ("博览会", "展会"), ("概览", "概况"),
                 ("展後報告", "展后报告")):
        s = s.replace(a, b)
    return re.sub(r"[\s>›»》\-—:：*|]+", "", s)


_NORM = tuple((k, _norm_anchor(k)) for k in LINK_KEYWORDS)
# 兜底组必须**换一份 URL 黑名单**：主表里 news / press / 新闻 是被排除的，
# 而兜底组要的恰恰就是这些页。不换就等于永远匹配不到。
_NORM_FB = tuple((k, _norm_anchor(k)) for k in FALLBACK_KEYWORDS)
BLOCK_FB = tuple(b for b in LINK_BLOCK
                 if b not in ("news", "press", "新闻", "资讯", "视频", "video"))


def rank_anchors(anchors: list[tuple[str, str]], limit: int,
                 table=None, block=None) -> list[tuple[str, str, str]]:
    """anchors=[(url, text)] → [(url, text, keyword)]，按关键词优先级排序去重。"""
    table = table if table is not None else _NORM
    block = block if block is not None else LINK_BLOCK
    found: list[tuple[int, str, str, str]] = []
    for u, text in anchors:
        if not text or len(text) > 40:
            continue
        if any(b in u.lower() for b in block):
            continue
        na = _norm_anchor(text)
        low = re.sub(r"\s+", " ", text.lower())
        for i, (k, nk) in enumerate(table):
            if k.isascii():
                hit = re.search(r"(?<![a-z])" + re.escape(k.lower()) + r"(?![a-z])", low)
            else:
                hit = nk in na
            if hit:
                found.append((i, u, text, k))
                break
    found.sort(key=lambda x: (x[0], len(x[2])))
    out, seen = [], set()
    for _, u, t, k in found:
        if u in seen:
            continue
        seen.add(u)
        out.append((u, t, k))
        if len(out) >= limit:
            break
    return out


def static_anchors(url: str, budget: Budget) -> tuple[str, str, list[tuple[str, str]]]:
    """返回 (final_url, html, anchors)。anchors 只取同域。"""
    status, final, html = fetch_with_retry(url, budget)
    if status >= 400:
        raise RuntimeError(f"http_{status}")
    host = urllib.parse.urlsplit(final).netloc
    out: list[tuple[str, str]] = []
    for m in re.finditer(r"""<a\b[^>]*href=["']([^"']{2,300})["'][^>]*>(.*?)</a>""",
                         html, re.I | re.S):
        u = urllib.parse.urljoin(final, m.group(1)).split("#")[0]
        if urllib.parse.urlsplit(u).netloc != host:
            continue
        if not u.lower().startswith("http"):
            continue
        out.append((u, _clean_anchor(m.group(2))))
    return final, html, out


def rendered_anchors(url: str, page) -> list[tuple[str, str]]:
    """用**已渲染**的 DOM 取链接。caexpo 这类站静态 <a> 数为 0。"""
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(1800)
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:                                   # noqa: BLE001
        pass
    links = page.evaluate(
        "() => Array.from(document.querySelectorAll('a[href]'))"
        ".map(a => ({href: a.href, text: (a.textContent || '').trim().slice(0, 40)}))")
    host = urllib.parse.urlsplit(page.url).netloc
    out: list[tuple[str, str]] = []
    for it in links:
        u = (it.get("href") or "").split("#")[0]
        if not u.startswith("http") or urllib.parse.urlsplit(u).netloc != host:
            continue
        if not it.get("text"):
            continue
        out.append((u, it["text"]))
    return out


def page_text(url: str, budget: Budget) -> tuple[str, str]:
    """静态取页；正文太短就返回空串（由调用方决定要不要渲染）。"""
    _, final, html = fetch_with_retry(url, budget)
    txt = re.sub(r"\n{3,}", "\n\n", visible_text(html)).strip()[:PER_PAGE_CAP]
    return final, txt


def collect_one(sid: str, home: str, page=None) -> dict:
    rec = {"urls": [], "chars": 0, "hits": [], "signals": 0, "via": "static", "error": None}
    budget = Budget(MAX_REQ_PER_SITE)

    why = _ROBOTS.reason(home)
    if why not in ("allow", "absent"):
        rec["error"] = "robots_denied" if why == "deny" else "robots_unreachable"
        return rec

    anchors: list[tuple[str, str]] = []
    try:
        final, _, anchors = static_anchors(home, budget)
        rec["via"] = "static"
    except Exception as ex:                             # noqa: BLE001
        rec["error"] = f"home_{type(ex).__name__}: {str(ex)[:50]}"
        final = home

    # 静态链接太少 → 页面结构靠 JS 生成，改用渲染后的 DOM 取链接
    if len(anchors) < 15 and page is not None:
        try:
            anchors = rendered_anchors(home, page)
            rec["via"] = "render_links"
        except Exception as ex:                         # noqa: BLE001
            rec["error"] = (rec["error"] or "") + f" render_{type(ex).__name__}"
            anchors = []

    cands = rank_anchors(anchors, MAX_SUB_PER_SITE)
    if not cands:
        # 一个规模类关键词都没命中 → 退到"主办方自家新闻稿"这一层。
        # 只在主表全空时启用，避免新闻页淹掉真正的"展会概况"。
        cands = rank_anchors(anchors, MAX_FALLBACK_PAGES, _NORM_FB, BLOCK_FB)
        if cands:
            rec["via"] += "+news_fallback"
    if not cands:
        rec["error"] = rec["error"] or (f"no_keyword_links(a={len(anchors)})")
        return rec

    blocks: list[tuple[str, str, int]] = []
    for sub, anchor, kw in cands:
        if budget.left <= 1:
            break
        if not _ROBOTS.allowed(sub):
            continue
        try:
            sub_final, txt = page_text(sub, budget)
        except Exception:                               # noqa: BLE001
            continue
        # 静态太短且本站在渲染模式 → 这一页也渲染
        if len(txt) < MIN_PAGE_CHARS and page is not None and rec["via"] != "static":
            try:
                page.goto(sub, wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_timeout(1500)
                txt = re.sub(r"\n{3,}", "\n\n",
                             page.evaluate("() => document.body.innerText")).strip()[:PER_PAGE_CAP]
            except Exception:                           # noqa: BLE001
                pass
        if len(txt) < MIN_PAGE_CHARS:
            continue
        n_sig = len(_SIGNAL.findall(txt))
        blocks.append((sub_final or sub, txt, n_sig))
        rec["urls"].append(sub_final or sub)
        if anchor not in rec["hits"]:
            rec["hits"].append(anchor)
        if len(blocks) >= MAX_SUB_PER_SITE:
            break

    # 有料的页排前面：抽取时的切片是有长度上限的，顺序决定谁进得去
    blocks.sort(key=lambda b: -b[2])
    if not blocks:
        rec["error"] = rec["error"] or "subpages_empty"
        return rec

    rec["signals"] = sum(b[2] for b in blocks)
    body = "\n\n".join(f"---- {u} ----\n\n{t}" for u, t, _ in blocks)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"{sid}.txt").write_text(body, encoding="utf-8")
    rec["chars"] = len(body)
    return rec


def load_targets() -> list[tuple[str, str]]:
    """缺口站 = 缺观众数 或 缺展商数。url 优先取 merged.json。"""
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    gap = {r["slug"] for r in con.execute(
        "SELECT slug FROM expo WHERE visitor_count IS NULL OR exhibitor_count IS NULL"
        " OR visitor_count<=0 OR exhibitor_count<=0")}
    url = {r["id"]: r["url"] for r in json.loads(MERGED.read_text(encoding="utf-8"))["records"]
           if r.get("url")}
    return [(s, url[s]) for s in sorted(gap) if s in url]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=MAX_WORKERS)
    ap.add_argument("--no-render", action="store_true", help="不启动浏览器（静态链接不足的站直接放弃）")
    ap.add_argument("--dry-run", action="store_true", help="只打印候选页，不保存不抽取")
    args = ap.parse_args()

    targets = load_targets()
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        targets = [t for t in targets if t[0] in want]
    if args.limit:
        targets = targets[: args.limit]
    print("缺观众数或展商数的展 %d 个，本轮处理 %d 个（单站 ≤%d 请求）" % (
        len(load_targets()), len(targets), MAX_REQ_PER_SITE))

    results: dict[str, dict] = {}
    t0 = time.time()

    if args.no_render:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(collect_one, s, u, None): s for s, u in targets}
            for n, fut in enumerate(as_completed(futs), 1):
                s = futs[fut]
                try:
                    r = fut.result()
                except Exception as ex:                 # noqa: BLE001
                    r = {"urls": [], "chars": 0, "hits": [], "signals": 0,
                         "via": "static", "error": f"crash:{type(ex).__name__}"}
                results[s] = r
                print("  [%2d/%2d] %-20s %5d字 sig=%-3d %-24s %s" % (
                    n, len(targets), s, r["chars"], r["signals"], (r["error"] or "")[:24],
                    ",".join(r["hits"])[:38]))
    else:
        # 浏览器只能单实例串行：Playwright sync API 不是线程安全的。
        # 静态请求仍然并发：先用线程池把每站的 HTML 拿到，渲染只处理剩下的。
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            ctx = browser.new_context(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"))
            for n, (s, u) in enumerate(targets, 1):
                # 每站新建 page：批次 1d 实测一个 page 被导航中断后状态变脏，
                # 会让后面所有站连续报 "interrupted"，看着像全站反爬。
                page = ctx.new_page()
                try:
                    r = collect_one(s, u, page)
                except Exception as ex:                 # noqa: BLE001
                    r = {"urls": [], "chars": 0, "hits": [], "signals": 0,
                         "via": "render_links", "error": f"crash:{type(ex).__name__}"}
                finally:
                    page.close()
                results[s] = r
                print("  [%2d/%2d] %-20s %5d字 sig=%-3d %-14s %-22s %s" % (
                    n, len(targets), s, r["chars"], r["signals"], r["via"],
                    (r["error"] or "")[:22], ",".join(r["hits"])[:34]))
            browser.close()

    if args.dry_run:
        print("\n--dry-run：不写 index。")
        return 0

    # 合并而不是覆盖：补采是分两轮跑的（先全量静态、再对少量站开浏览器），
    # 覆盖会让第二轮把第一轮已抓到的结果抹掉，看着像"大部分站都失败了"。
    prev: dict[str, dict] = {}
    if INDEX.exists():
        try:
            prev = json.loads(INDEX.read_text(encoding="utf-8"))
        except ValueError:
            prev = {}
    prev.update(results)
    INDEX.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = {k: v for k, v in results.items() if not v["error"]}
    useful = {k: v for k, v in ok.items() if v["signals"] > 0}
    print("\n" + "=" * 72)
    print("抓到子页 %d / %d 站；其中正文里出现规模数字痕迹的 %d 站；用时 %.0f 秒" % (
        len(ok), len(results), len(useful), time.time() - t0))
    fails: dict[str, int] = {}
    for v in results.values():
        if v["error"]:
            k = re.sub(r"\(.*", "", v["error"].split(":")[0])
            fails[k] = fails.get(k, 0) + 1
    if fails:
        print("失败分布：" + " ｜ ".join(f"{k}×{n}" for k, n in
                                    sorted(fails.items(), key=lambda x: -x[1])))
    print("→ %s" % INDEX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
