"""
批次 2b：给"首页抽不到规模字段"的展会补抓子页正文。

背景：
    批次 2 从 batch1 首页正文里抽观众数/展商数/面积，81 个有正文的站里 26 个
    一个字段都没抽到（44 个站至少缺一个规模字段）。首页通常只放导航与口号，
    "展会概况/上届回顾/展后报告"这类页才写规模数据。

做法：
    · 候选站 = data/batch2/scale.json 里 ok=false，或 fields 不含
      visitor_count / exhibitor_count / exhibition_area 的 id。
    · txt 是纯文本，抽不出原始链接，所以重新请求首页 HTML，按 <a> 的
      **链接文字**（不是 URL 路径）挑子页 —— SiteServer/CMS 的站
      /contents/101/14166.html 这种路径里根本没有 about/概况。
    · 抓取、清洗、robots、编码识别全部复用 collect_skeleton.py，
      保证新正文与批次 1 的口径完全一致（否则重抽时会引入方法差）。
    · 每站 ≤5 次请求（含重试），最多 3 个子页，避免把整站爬一遍。

落盘：
    data/batch1/sub/<id>.txt      多页用 "---- <url> ----" 分隔，保留来源 URL
    data/batch1/sub_index.json    {id: {urls, chars, hits, error}}

用法：
    python scripts/persona/collect_subpages.py                 # 默认最多 30 站
    python scripts/persona/collect_subpages.py --limit 3
    python scripts/persona/collect_subpages.py --only ciie,scie
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                      # expohub-backend
DATA = ROOT / "data"
BATCH1 = DATA / "batch1"
SUB_DIR = BATCH1 / "sub"
INDEX = BATCH1 / "sub_index.json"
SCALE = DATA / "batch2" / "scale.json"
CANDIDATES = DATA / "expo_candidates_final.json"
RAW_DIR = BATCH1 / "raw"
RENDERED_DIR = BATCH1 / "rendered"

# 复用批次 1 的抓取与清洗口径（同一个 _OPENER：绕系统代理 + 放宽证书；
# 同一个 visible_text：去 script/style、html.unescape、压空白）。
sys.path.insert(0, str(HERE))
from collect_skeleton import (  # noqa: E402
    _OPENER, _ROBOTS, TIMEOUT, USER_AGENT, fetch, visible_text,
)

SCALE_KEYS = ("visitor_count", "exhibitor_count", "exhibition_area")

# 链接文字关键词。顺序即优先级：越靠前越可能是"专门讲规模"的页。
LINK_KEYWORDS = (
    "展会概况", "展会介绍", "展会简介", "关于展会", "上届回顾", "往届回顾",
    "展会数据", "展会规模", "展后报告",
    "Exhibition Profile", "Why Exhibit", "About", "Overview", "Facts",
    "Figures", "Statistics", "Review",
)
# 导航/功能页，命中文字也不抓。
# 注意别写 "en/"：/humen/list_270.html 里就含 "en/"，会把"展会介绍"整个误杀。
LINK_BLOCK = ("login", "register", "signin", "signup", "news", "press", "download",
              "video", "member", "cart", "pay", "subscribe", "contact", "privacy",
              "新闻", "资讯", "下载", "视频", "直播", "登录", "注册", "会员", "招聘",
              "联系我们", "隐私", "版权", "网站地图", "lang=",
              ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".doc",
              "javascript:", "mailto:", "tel:")

MAX_SUB_PER_SITE = 3
MAX_REQ_PER_SITE = 5
MAX_WORKERS = 6
MIN_PAGE_CHARS = 120          # 低于这个字数的页面多半是跳转页/占位页
PER_PAGE_CAP = 20_000         # 单页正文上限，防止 404 站返回整个站点地图


class Budget:
    """单站请求预算。重试也计数 —— 否则一个 flaky 站能吃掉 15 次请求。"""

    def __init__(self, n: int = MAX_REQ_PER_SITE):
        self.left = n

    def take(self) -> None:
        if self.left <= 0:
            raise RuntimeError("request_budget_exhausted")
        self.left -= 1


def fetch_with_retry(url: str, budget: Budget, attempts: int = 3) -> tuple[int, str, str]:
    last: Exception | None = None
    for i in range(attempts):
        budget.take()
        try:
            return fetch(url, timeout=TIMEOUT)
        except Exception as ex:                        # noqa: BLE001
            last = ex
            # 明确"没有这个页"不必重试，别把 3 次机会耗在 404 上
            if isinstance(ex, urllib.error.HTTPError) and 400 <= ex.code < 500 and ex.code != 429:
                break
            if isinstance(ex, RuntimeError):
                break
            if i + 1 < attempts:
                time.sleep(0.6 * (i + 1))
    raise last if last else RuntimeError("unknown_fetch_error")


def _clean_anchor(inner: str) -> str:
    a = re.sub(r"<[^>]+>", " ", inner)
    return re.sub(r"\s+", " ", a).strip()


def _norm_anchor(s: str) -> str:
    """归一化后再比关键词。

    · 去空白：`关于<span>展会</span>` 提出来是"关于 展会"，直接子串匹配会漏。
    · 展览会/博览会 → 展会："展览会简介"与"展会简介"是同一个东西（chinacoat 就这么写）。
    · 概览 → 概况：ITES（simm）导航写"展会概览"。
    只做词形归并，不扩充关键词表。
    """
    s = s.lower()
    for a, b in (("展览会", "展会"), ("博览会", "展会"), ("概览", "概况")):
        s = s.replace(a, b)
    return re.sub(r"[\s>›»》\-—:：*]+", "", s)


_NORM_KEYWORDS = tuple((k, _norm_anchor(k)) for k in LINK_KEYWORDS)


def pick_subpages(html: str, base_url: str, limit: int = MAX_SUB_PER_SITE) -> list[tuple[str, str, str]]:
    """返回 [(url, anchor, keyword)]，按关键词优先级排序。

    只跟同域链接；跳过锚点/功能页；链接文字里必须命中规模类关键词。
    """
    host = urllib.parse.urlsplit(base_url).netloc
    base = base_url.split("#")[0]
    seen = {base, base.rstrip("/")}
    found: list[tuple[int, str, str, str]] = []
    for m in re.finditer(r"""<a\b[^>]*href=["']([^"']{2,300})["'][^>]*>(.*?)</a>""",
                         html, re.I | re.S):
        href, inner = m.group(1), m.group(2)
        anchor = _clean_anchor(inner)
        if not anchor or len(anchor) > 40:
            continue
        u = urllib.parse.urljoin(base_url, href).split("#")[0]
        low_u = u.lower()
        if urllib.parse.urlsplit(u).netloc != host:
            continue
        if u in seen:
            continue
        if any(b in low_u for b in LINK_BLOCK):
            continue
        # 关键词命中：中文按归一化子串；英文按字母边界（避免 "review" 命中 "preview"）。
        # 英文必须用**保留空格**的文本匹配 —— 归一化把空格去掉后，
        # "About Tea Fair" 会变成 "aboutteafair"，\b 与字母边界都会失配。
        na = _norm_anchor(anchor)
        low = re.sub(r"\s+", " ", anchor.lower())
        kw = ""
        for i, (k, nk) in enumerate(_NORM_KEYWORDS):
            if k.isascii():
                if re.search(r"(?<![a-z])" + re.escape(k.lower()) + r"(?![a-z])", low):
                    kw = k
                    found.append((i, u, anchor, kw))
                    break
            elif nk in na:
                kw = k
                found.append((i, u, anchor, kw))
                break
        if not kw:
            continue
        seen.add(u)
        seen.add(u.rstrip("/"))

    found.sort(key=lambda x: (x[0], len(x[2])))
    out: list[tuple[str, str, str]] = []
    urls: set[str] = set()
    for _, u, anchor, kw in found:
        if u in urls:
            continue
        urls.add(u)
        out.append((u, anchor, kw))
        if len(out) >= limit:
            break
    return out


def _home_url(sid: str, api_url: str | None) -> str | None:
    if api_url:
        return api_url
    p = RAW_DIR / f"{sid}.txt"
    if p.exists():
        m = re.search(r"^URL:\s*(\S+)", p.read_text(encoding="utf-8", errors="ignore"), re.M)
        if m:
            return m.group(1)
    return None


def collect_one(sid: str, url: str) -> dict:
    rec = {"urls": [], "chars": 0, "hits": [], "error": None}
    budget = Budget()

    why = _ROBOTS.reason(url)
    if why not in ("allow", "absent"):
        rec["error"] = "robots_denied" if why == "deny" else "robots_unreachable"
        return rec

    try:
        status, final, home_html = fetch_with_retry(url, budget)
    except Exception as ex:                            # noqa: BLE001
        rec["error"] = f"home_fetch_{type(ex).__name__}: {str(ex)[:60]}"
        return rec
    if status >= 400:
        rec["error"] = f"home_http_{status}"
        return rec

    cands = pick_subpages(home_html, final)
    if not cands:
        # 首页 <a> 极少 => 纯前端壳（批次 1 里那 19 个渲染站就是这种）
        n_a = len(re.findall(r"<a\b", home_html, re.I))
        rec["error"] = "spa_shell_no_links" if n_a < 15 else "no_keyword_links"
        return rec

    blocks: list[tuple[str, str]] = []
    for sub, anchor, kw in cands:
        if budget.left <= 0:
            break
        if not _ROBOTS.allowed(sub):
            continue
        try:
            _, sub_final, sub_html = fetch_with_retry(sub, budget)
        except Exception:                              # noqa: BLE001
            continue
        txt = visible_text(sub_html)
        txt = re.sub(r"\n{3,}", "\n\n", txt).strip()[:PER_PAGE_CAP]
        if len(txt) < MIN_PAGE_CHARS:
            continue                                   # 跳转页/空壳，不算命中
        blocks.append((sub_final or sub, txt))
        rec["urls"].append(sub_final or sub)
        if anchor not in rec["hits"]:
            rec["hits"].append(anchor)

    if not blocks:
        rec["error"] = "subpages_empty_or_unreachable"
        return rec

    body = "\n\n".join(f"---- {u} ----\n\n{t}" for u, t in blocks)
    SUB_DIR.mkdir(parents=True, exist_ok=True)
    (SUB_DIR / f"{sid}.txt").write_text(body, encoding="utf-8")
    rec["chars"] = len(body)
    return rec


def load_targets() -> list[tuple[str, str | None]]:
    scale = json.loads(SCALE.read_text(encoding="utf-8"))
    bad: list[str] = []
    for r in scale["records"]:
        if not r.get("ok") or not any(k in (r.get("fields") or {}) for k in SCALE_KEYS):
            bad.append(r["id"])

    api = {}
    if CANDIDATES.exists():
        for e in json.loads(CANDIDATES.read_text(encoding="utf-8")).get("expos", []):
            if e.get("url"):
                api[e["id"]] = e["url"]

    # 纯前端站首页 HTML 里没有链接，1 次请求也只能得到 "spa_shell_no_links"。
    # 优先把预算花在静态页站上；SPA 排在后面，名额够才轮到。
    spa = {p.stem for p in RENDERED_DIR.glob("*.txt")} if RENDERED_DIR.exists() else set()
    ordered = [i for i in bad if i not in spa] + [i for i in bad if i in spa]
    return [(i, _home_url(i, api.get(i))) for i in ordered]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = ap.parse_args()

    targets = load_targets()
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        targets = [t for t in targets if t[0] in want][:args.limit or None]
    elif args.limit:
        targets = targets[: args.limit]

    todo = [(i, u) for i, u in targets if u]
    skipped = [i for i, u in targets if not u]
    print("缺规模字段的站 %d 个；本轮处理 %d 个（并发 %d，单站 ≤%d 请求）" % (
        len(targets), len(todo), args.workers, MAX_REQ_PER_SITE))

    results: dict[str, dict] = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=min(args.workers, MAX_WORKERS)) as pool:
        futs = {pool.submit(collect_one, i, u): i for i, u in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            sid = futs[fut]
            try:
                r = fut.result()
            except Exception as ex:                    # noqa: BLE001
                r = {"urls": [], "chars": 0, "hits": [], "error": f"crash: {type(ex).__name__}"}
            results[sid] = r
            print("  [%2d/%2d] %-18s %5d 字  %-28s %s" % (
                n, len(todo), sid, r["chars"], (r["error"] or "")[:28],
                ",".join(r["hits"])[:40]))

    for sid in skipped:
        results[sid] = {"urls": [], "chars": 0, "hits": [], "error": "no_url"}

    order = {i: n for n, (i, _) in enumerate(targets)}
    out = {i: results[i] for i in sorted(results, key=lambda x: order.get(x, 999))}
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = [v for v in out.values() if not v["error"]]
    print("\n" + "=" * 68)
    print("补到子页 %d / %d 站，平均 %d 字，用时 %.0f 秒" % (
        len(ok), len(out), sum(v["chars"] for v in ok) / max(len(ok), 1), time.time() - t0))
    fails: dict[str, int] = {}
    for v in out.values():
        if v["error"]:
            k = re.sub(r"_?\d+$", "", v["error"].split(":")[0])
            fails[k] = fails.get(k, 0) + 1
    if fails:
        print("失败分布：" + " ｜ ".join(f"{k}×{n}" for k, n in sorted(fails.items(), key=lambda x: -x[1])))
    print("→ %s" % INDEX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
