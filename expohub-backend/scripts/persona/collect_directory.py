"""
批次 3：展商名录可得性 + E2 竞品数（同展内与目标品类相同的展商数量）。

两段式，先复用再爬：

  A 复用段  把 persona.db 的 94 个样本展与主库 exhibitions 的 12 个正式展按
            核心名做匹配（去年份 / 届次 / "国际" / "中国" / "展览会" 等噪声）。
            命中即直接读 catalog_exhibitors + exhibition_exhibitors 统计名录条数与
            industry 分布 —— 不重复爬已经有的东西。

  B 爬取段  只对未命中的展，去官网找"展商名录"页，**只取统计量与结构**：
            名录是否存在、条数（声明值或 页数×每页条数）、是否有品类字段。
            不抓展商明细。按批次 1 正文里名录关键词的强弱排序取前 N 个（默认 20），
            单站最多 4 个页面（首页 + 3 个候选名录页），不留死角也不死磕。

抓取层完全复用 collect_skeleton（_OPENER 放宽证书、robots 三态、gzip、编码识别、
UA 带联系方式、15s 超时），只是额外套了 3 次重试。

用法：
    python scripts/persona/collect_directory.py                 # 复用 + 爬 20 站
    python scripts/persona/collect_directory.py --reuse-only     # 只做复用匹配
    python scripts/persona/collect_directory.py --max-sites 3 --only gile,ccmt
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# 统一复用批次 1 的抓取实现，不另写一套
from collect_skeleton import TIMEOUT, _ROBOTS, fetch, visible_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PERSONA_DB = ROOT / "persona.db"
EXPO_DB = ROOT / "expohub.db"
CANDIDATES = ROOT / "data" / "expo_candidates_final.json"
BATCH1 = ROOT / "data" / "batch1"
BATCH2_SCALE = ROOT / "data" / "batch2" / "scale.json"
OUT_DIR = ROOT / "data" / "batch3"
OUT_JSON = OUT_DIR / "directory.json"

RETRY = 3
MAX_REQ_PER_SITE = 5          # 首页 1 + 名录候选 3，留 1 次余量
MAX_DIR_CANDIDATES = 3

# ---------------------------------------------------------------- 名称归一

def norm_name(s: str | None) -> str:
    """把展会名压成核心名，用于跨库比对。

    只做"去掉确定无语义的片段"，不做同义词归并 —— 归并一旦放宽
    （比如把"机床"和"机械"视为同一），就会把 CMES 华机展错配到 CCMT，
    这类错配在名录统计里是致命的：数字看着合理，来源却是另一个展。
    """
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", s)
    t = re.sub(r"(19|20)\d{2}", "", t)
    t = re.sub(r"第\s*[0-9一二三四五六七八九十百]+\s*届", "", t)
    t = t.lower()
    t = re.sub(r"[\W_]+", "", t)
    for w in ("国际", "中国", "展览会", "博览会", "展会", "交易会", "展览", "展示"):
        t = t.replace(w, "")
    return t


def match_reuse(persona: list[dict], exhs: list[dict]) -> list[dict]:
    """核心名互为子串且长度 ≥4 才算命中。返回命中列表（含双向证据）。"""
    out = []
    for e in exhs:
        ne = norm_name(e["title"])
        if len(ne) < 4:
            continue
        for p in persona:
            for cand in (p["name_cn"], p["name_en"]):
                np = norm_name(cand)
                if len(np) < 4:
                    continue
                if np == ne or np in ne or ne in np:
                    out.append({
                        "slug": p["slug"], "exhibition_id": e["id"],
                        "exhibition_title": e["title"],
                        "matched_on": cand, "persona_name": p["name_cn"],
                        "key_persona": np, "key_exhibition": ne,
                        "method": "exact_norm" if np == ne else "substring_norm",
                    })
                    break
            else:
                continue
            break
    return out


# ---------------------------------------------------------------- 品类 → industry

# catalog_exhibitors.industry 是自由文本（"医疗器械制造" / "Medical devices manu" /
# "其他" 并存），没有外键也没有字典表。E2 要数"同品类展商"，只能靠关键词映射。
# 这张表是**唯一**的品类判定依据，宁可漏判（→ 竞品数偏小）也不要乱判：
# 竞品数偏大会让 E2 分数虚假变低，进而误导出"这个展竞争不激烈"的结论。
CATEGORY_INDUSTRY = {
    "日用消费品": ["日用", "百货", "日化", "母婴", "孕婴童", "消费品", "家居用品", "清洁"],
    "综合服务": ["服务", "物流", "供应链", "贸易", "电商", "跨境", "会展", "金融", "咨询", "零售"],
    "食品": ["食品", "饮料", "咖啡", "茶", "烘焙", "焙烤", "酒", "餐饮", "食材", "调味", "乳"],
    "办公箱包及休闲用品": ["文具", "办公", "箱包", "休闲", "户外", "体育", "运动", "露营", "钓"],
    "医药及医疗保健": ["医疗", "医药", "制药", "器械", "原料药", "健康", "营养", "保健", "生物", "药品"],
    "五金工具": ["五金", "工具", "模具", "磨料", "紧固件", "机床工具", "刃具"],
    "机械": ["机械", "机床", "工业", "自动化", "装备", "制造", "机器人", "激光", "焊接", "铸造"],
    "建材": ["建材", "陶瓷", "门窗", "幕墙", "卫浴", "石材", "建筑", "水泥", "玻璃"],
    "礼品": ["礼品", "赠品", "工艺品", "促销品"],
    "纺织服装": ["纺织", "服装", "面料", "辅料", "家纺", "纱线", "针织", "印染"],
    "家居装饰品": ["家居", "家具", "装饰", "软装", "家装", "布艺", "地毯"],
    "电子及家电": ["家电", "电子", "电器", "3c", "智能家居", "视听", "影音"],
    "照明": ["照明", "灯具", "灯饰", "led", "光源"],
    "车辆及配件": ["汽车", "车辆", "零配件", "汽配", "轮胎", "摩托车", "自行车", "电动车", "改装"],
    "化工产品": ["化工", "涂料", "油墨", "橡塑", "塑料", "橡胶", "化学", "树脂", "颜料"],
    "能源": ["能源", "储能", "风电", "风能", "光伏", "电力", "电池", "氢", "核电", "电网"],
    "鞋类": ["鞋", "皮革", "皮具"],
    "AI/科技": ["人工智能", "科技", "半导体", "集成电路", "软件", "数字", "芯片", "光电",
                "新材料", "低空", "科研", "信息技术", "大数据"],
}


def industry_matches(industry: str | None, category: str | None) -> bool:
    if not industry or not category:
        return False
    kws = CATEGORY_INDUSTRY.get(category)
    if not kws:
        return False
    low = industry.lower()
    return any(k in low for k in kws)


# ---------------------------------------------------------------- 复用段统计

def reuse_stats(conn: sqlite3.Connection, exhibition_id: int, category: str | None) -> dict:
    rows = conn.execute(
        "SELECT c.industry FROM catalog_exhibitors c "
        "JOIN exhibition_exhibitors e ON e.catalog_exhibitor_id = c.id "
        "WHERE e.exhibition_id = ?", (exhibition_id,)).fetchall()
    listing_count = len(rows)
    dist = Counter((r[0] or "").strip() for r in rows)
    labeled = sum(1 for r in rows if (r[0] or "").strip() not in ("", "其他", "Others", "other"))
    comp = sum(1 for r in rows if industry_matches(r[0], category))
    return {
        "listing_count": listing_count,
        "industry_dist": dict(dist.most_common(12)),
        "labeled": labeled,
        "competitor_count": comp,
    }


# ---------------------------------------------------------------- 名录页识别

DIR_STRONG = ("展商名录", "参展商名录", "参展名录", "展商列表", "参展商列表",
              "展商查询", "参展商查询", "展商中心", "参展企业", "exhibitor list",
              "exhibitor directory", "exhibitor search", "find exhibitor")
DIR_WEAK = ("展商", "参展商", "名录", "exhibitor", "directory")
BLOCK = ("login", "register", "signin", "signup", "cart", "pay", ".pdf", ".jpg",
         ".png", ".zip", "javascript:", "mailto:", "tel:", ".mp4")
def find_dir_links(html: str, base: str, limit: int = MAX_DIR_CANDIDATES) -> list[tuple[int, str, str]]:
    """从首页挑"名录"入口。按锚文字权重排序，同域、去重、最多 limit 个。"""
    host = urllib.parse.urlsplit(base).netloc
    seen: set[str] = set()
    scored: list[tuple[int, str, str]] = []
    for m in re.finditer(r"""<a\b[^>]*href=["']([^"']{2,300})["'][^>]*>(.*?)</a>""",
                         html, re.I | re.S):
        href, inner = m.group(1), m.group(2)
        anchor = re.sub(r"<[^>]+>", "", inner)
        anchor = re.sub(r"\s+", "", anchor).lower()
        if not anchor or len(anchor) > 40:
            continue
        u = urllib.parse.urljoin(base, href).split("#")[0]
        if urllib.parse.urlsplit(u).netloc != host or u in seen:
            continue
        low = u.lower()
        if any(b in low for b in BLOCK):
            continue
        score = 0
        if any(k in anchor for k in DIR_STRONG):
            score += 20
        elif any(k in anchor for k in DIR_WEAK):
            score += 8
        if any(k in low for k in ("exhibitor", "exhibitors", "/dir", "directory", "list")):
            score += 6
        if anchor in ("名录", "展商", "参展商"):
            score += 4
        if score:
            seen.add(u)
            scored.append((score, u, anchor))
    scored.sort(key=lambda x: -x[0])
    return scored[:limit]


# 声明的名录总数。中文站最常见的三种写法：共 1234 家展商 / 展商 1234 家 / 共 1234 条
COUNT_PATTERNS = (
    r"共\s*(\d{1,6})\s*(?:家|个|位)?\s*(?:参展商|展商|参展企业|企业)",
    r"(\d{1,6})\s*家\s*(?:参展商|展商|参展企业)",
    r"(?:参展商|展商|参展企业)\s*(?:数量|总数)?\s*[:：]?\s*(\d{1,6})\s*(?:家|个)",
    r"共\s*(?:收录)?\s*(\d{1,6})\s*条",
    r"(?:total|found)\s*[:：]?\s*(\d{1,6})\s*(?:exhibitors|results|companies)?",
    r"(\d{1,6})\s*(?:exhibitors|companies|results)",
)
PAGE_PATTERNS = (
    r"共\s*(\d{1,4})\s*页",
    r"page\s*\d+\s*(?:of|/)\s*(\d{1,4})",
    r"/\s*(\d{1,4})\s*页",
)
# 只认"行业维度"的显式标签。不能收 "分类"/"category" 这种泛词：
# 页脚导航、产品筛选、新闻分类里都有一堆，收进来 has_industry 就恒为 True。
INDUSTRY_HINT = ("行业分类", "展商分类", "参展商分类", "所属行业", "行业类别", "按行业",
                 "展品分类", "展商行业", "industry category", "exhibitor category")
TITLE_DIR = ("展商名录", "参展商名录", "参展名录", "展商列表", "参展商列表",
             "展商查询", "参展商查询", "exhibitor list", "exhibitor directory",
             "exhibitors")
COMPANY_HINT = re.compile(
    r"有限公司|公司|集团|股份|实业|工厂|厂$|商行|经营部|科技|机械|设备|电子|材料|照明|"
    r"光电|仪器|包装|自动化|模具|工具|五金|轴承|电机|电气|泵|阀|化工|新材|智能|"
    r"co\.?,?\s*ltd|ltd\.?$|inc\.?$|llc|gmbh|corp|limited|group|technology|"
    r"industr|alliance|association|university|company", re.I)
NAV_TEXT = ("首页", "登录", "注册", "关于", "联系", "新闻", "下载", "更多", "more",
            "english", "中文", "简体", "繁体", "展会概况", "展会简介", "参展指南",
            "参观指南", "同期活动", "展馆介绍", "服务", "隐私", "免责", "版权")


def _anchors(html: str, base: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r"""<a\b[^>]*href=["']([^"']{2,300})["'][^>]*>(.*?)</a>""", html, re.I | re.S):
        anchor = re.sub(r"<[^>]+>", "", m.group(2))
        anchor = re.sub(r"\s+", " ", anchor).strip()
        if not (2 <= len(anchor) <= 40):
            continue
        full = urllib.parse.urljoin(base, m.group(1)).split("#")[0].rstrip("/")
        out.append((full, anchor))
    return out


def _nav_key(u: str) -> str:
    p = urllib.parse.urlsplit(u)
    return (p.netloc + p.path).rstrip("/").lower()


def analyze_listing(html: str, url: str, nav: set[str]) -> dict:
    """判定一页是否是名录页，并抽出统计量。抽不到就返回 None，不猜。

    nav 是从**首页**收集的导航地址集合。名录页的条目是首页上不会出现的详情链接，
    导航链接一定会在首页出现过 —— 用它做减法，比任何"锚文字长度/关键词"规则都稳。
    实测不加这步，ccmt 的展商名录页会被数成 55 条（全是导航），
    ccmt 真正的条目是 JS 渲染的，一条都不在静态 HTML 里。
    """
    text = visible_text(html)
    flat = re.sub(r"\s+", " ", text)
    mt = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title = re.sub(r"\s+", " ", mt.group(1)).strip() if mt else ""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    heading = re.sub(r"<[^>]+>|\s+", "", h1.group(1)) if h1 else ""
    by_title = any(k in (title + heading).lower() for k in TITLE_DIR)

    items: list[str] = []
    for u, a in _anchors(html, url):
        if _nav_key(u) in nav:
            continue
        if a.lower() in NAV_TEXT:
            continue
        items.append(a)
    per_page = len(items)
    # "像公司名"的比例。名录页这点很高；展品分类页/联系页/新闻页接近 0。
    # 这一步是为了挡掉 fhcchina 那种"标题写着 Exhibitor List、正文却是展品分类"
    # 的页面 —— 只看标题会把它记成 98 条名录。
    comp_ratio = (sum(1 for a in items if COMPANY_HINT.search(a)) / per_page) if per_page else 0.0

    declared, declared_ev = None, ""
    for pat in COUNT_PATTERNS:
        m = re.search(pat, flat, re.I)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 500_000:
                declared, declared_ev = v, m.group(0)[:60]
                break

    # SPA 站点常把初始数据塞在 HTML 里（__INITIAL_STATE__ / total: 1234），
    # 这比"数锚点"可靠得多，而且不用执行 JS。
    json_total = None
    mj = re.search(r'"(?:total|totalCount|total_count|totalNum|count)"\s*:\s*"?(\d{1,6})', html)
    if mj and 1 <= int(mj.group(1)) <= 500_000:
        json_total = int(mj.group(1))

    pages, pages_ev = None, ""
    for pat in PAGE_PATTERNS:
        m = re.search(pat, flat, re.I)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 2000:
                pages, pages_ev = v, m.group(0)[:40]
                break

    ind_hits = [h for h in INDUSTRY_HINT if h in flat]
    return {
        "title": title[:70], "heading": heading[:40],
        "by_title": by_title,
        "declared": declared, "declared_ev": declared_ev, "json_total": json_total,
        "pages": pages, "pages_ev": pages_ev,
        "per_page": per_page, "sample_names": items[:5],
        "company_ratio": round(comp_ratio, 3),
        "has_industry": bool(ind_hits), "industry_ev": ",".join(ind_hits[:3]),
        "text_len": len(flat),
    }


# ---------------------------------------------------------------- 爬取一段

def fetch_retry(url: str) -> tuple[int, str, str]:
    last: Exception | None = None
    for i in range(RETRY):
        try:
            return fetch(url, timeout=TIMEOUT)
        except Exception as ex:  # noqa: BLE001
            last = ex
            if i < RETRY - 1:
                time.sleep(0.6 * (i + 1))
    raise last  # type: ignore[misc]


DEBUG = False


def crawl_one(e: dict) -> dict:
    """单站观察。返回目录相关字段 + 明确的失败原因。"""
    slug, url = e["slug"], e.get("url")
    rec = {
        "slug": slug, "source": "none", "listing_count": None, "has_industry": None,
        "completeness": None, "competitor_count_by_category": None,
        "note": "", "target_category": e.get("category"), "has_listing_page": None,
    }
    if not url:
        rec["note"] = "crawl: 无官网 URL"
        return rec

    why = _ROBOTS.reason(url)
    if why not in ("allow", "absent"):
        rec["note"] = "crawl: robots_denied" if why == "deny" else "crawl: robots_unreachable"
        return rec

    try:
        status, final, html = fetch_retry(url)
    except Exception as ex:  # noqa: BLE001
        rec["note"] = "crawl: %s %s" % (type(ex).__name__, str(ex)[:40])
        return rec

    cands = find_dir_links(html, final)
    nav = {_nav_key(u) for u, _ in _anchors(html, final)}
    reqs = 1
    tried: list[str] = []
    best: dict | None = None
    for score, u, anchor in cands:
        if reqs >= MAX_REQ_PER_SITE - 1:
            break
        if not _ROBOTS.allowed(u):
            tried.append("%s robots_deny" % u)
            continue
        try:
            _, f2, h2 = fetch_retry(u)
            reqs += 1
        except Exception as ex:  # noqa: BLE001
            tried.append("%s %s" % (u, type(ex).__name__))
            continue
        tried.append(u)
        a = analyze_listing(h2, f2, nav)
        a["url"] = f2
        a["anchor"] = anchor
        # 名录页的判据是"页面自称名录 + 有列表结构"，不是"提到了总数"：
        # 展会简介页也写"共 1877 家展商"，那是规模数字不是名录条数。
        # 混起来会让 listing_count 变成 exhibitor_count 的复制品，完整度永远 100%。
        structured = (a["per_page"] >= 8 and a["company_ratio"] >= 0.35) or bool(a["json_total"])
        a["structured"] = structured
        a["label"] = bool(a["by_title"]) or any(k in anchor for k in TITLE_DIR)
        if DEBUG:
            print("    ? %-58s per=%-3s pg=%-3s decl=%-6s json=%-6s lbl=%-5s ratio=%-4s %s" % (
                f2[:58], a["per_page"], a["pages"], a["declared"], a["json_total"],
                a["label"], a["company_ratio"], a["title"][:24]))
        # 没有"名录"这个标签的页面一律不认。批次 3 的教训：
        # cwp 的 /newslist/1 有 9 个公司名（新闻里提到企业），b-catering 的
        # /productlistsz.html 有 165 件展品 —— 两者都会让 listing_count 变成别的量。
        rank = (2 if a["by_title"] else 0) + (1 if structured else 0) + (1 if a["declared"] else 0)
        a["rank"] = rank if a["label"] else 0
        if rank and a["label"] and (best is None or rank > best["rank"] or
                     (rank == best["rank"] and a["per_page"] > best["per_page"])):
            best = a

    if best is None:
        rec["has_listing_page"] = False
        rec["note"] = "crawl: 首页无名录入口" if not cands else "crawl: 候选页均非名录（%s）" % \
            ("; ".join(t.split("/")[-1][:40] for t in tried[:3]) or "无可抓")
        return rec

    # 页面自称"名录"但看不到条目：多半是 JS 渲染的名录。
    # 这时只能确认"名录存在"，条数是 null —— 不能拿简介页的规模数字顶替。
    if not best["structured"]:
        rec.update({
            "source": "crawl", "has_listing_page": bool(best["by_title"]),
            "listing_count": None,
            "has_industry": False,
            "note": "crawl: 名录页%s｜%s（per_page=%d company_ratio=%s title=%s），条数不可计%s" % (
                "存在" if best["by_title"] else "疑似",
                "条目为 JS 渲染，静态 HTML 无公司链接" if best["per_page"] < 8
                else "条目非公司名（疑似展品/分类导航）",
                best["per_page"], best["company_ratio"], best["title"][:26] or "无标题",
                "｜声明值 %d 无列表结构，已弃用" % best["declared"] if best["declared"] else ""),
        })
        return rec

    est = None
    if best["declared"]:
        est, how = best["declared"], "declared"
    elif best["json_total"]:
        est, how = best["json_total"], "json_total"
    elif best["pages"] and best["per_page"]:
        est, how = best["pages"] * best["per_page"], "pages*per_page"
    else:
        est, how = best["per_page"], "per_page_only"

    rec.update({
        "source": "crawl", "has_listing_page": True,
        "listing_count": est, "listing_method": how,
        "has_industry": bool(best["has_industry"]),
        "note": "crawl: %s via %s（%s）｜pages=%s per_page=%s company_ratio=%s%s 页面=%s" % (
            how, best["anchor"][:20], best["declared_ev"] or best["pages_ev"] or "n/a",
            best["pages"], best["per_page"], best["company_ratio"],
            "｜仅单页可见，为下界" if how == "per_page_only" else "", best["url"]),
        "_industry_ev": best["industry_ev"],
        "_sample": best["sample_names"],
        "_reqs": reqs,
    })
    return rec


def pick_crawl_targets(slugs: list[str], limit: int, only: set[str]) -> list[str]:
    """按批次 1 正文里名录关键词的强弱排序 —— 这是一个**乐观偏置**的抽样：
    挑的是"看起来最有名录"的展，所以得到的可得率是上界，不是总体估计。"""
    if only:
        return [s for s in slugs if s in only]
    strong = ("展商名录", "参展商名录", "参展名录", "展商列表", "参展商列表",
              "展商查询", "exhibitor list", "exhibitors list")
    scored = []
    for s in slugs:
        p = BATCH1 / "raw" / f"{s}.txt"
        if not p.exists():
            p = BATCH1 / "rendered" / f"{s}.txt"
        t = p.read_text(encoding="utf-8", errors="ignore").lower() if p.exists() else ""
        scored.append((sum(t.count(k) for k in strong), s))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s for _, s in scored[:limit]]


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-sites", type=int, default=20)
    ap.add_argument("--only", default="")
    ap.add_argument("--reuse-only", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    global DEBUG
    DEBUG = args.debug
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    pconn = sqlite3.connect(f"file:{PERSONA_DB}?mode=ro", uri=True)
    pconn.row_factory = sqlite3.Row
    persona = [dict(r) for r in pconn.execute(
        "SELECT id, slug, name_cn, name_en, city, exhibitor_count FROM expo ORDER BY id")]
    mconn = sqlite3.connect(f"file:{EXPO_DB}?mode=ro", uri=True)
    mconn.row_factory = sqlite3.Row
    exhs = [dict(r) for r in mconn.execute(
        "SELECT id, title, title_en FROM exhibitions ORDER BY id")]

    cand = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    category = {e["id"]: e.get("category") for e in cand["expos"]}
    url = {e["id"]: e.get("url") for e in cand["expos"]}
    status = {e["id"]: e.get("status") for e in cand["expos"]}

    # 展商总数：优先 persona.db（批次 2 落库），缺失时回落到 scale.json
    scale = {}
    if BATCH2_SCALE.exists():
        for r in json.loads(BATCH2_SCALE.read_text(encoding="utf-8"))["records"]:
            v = (r.get("fields") or {}).get("exhibitor_count") or {}
            if v.get("value"):
                scale[r["id"]] = v["value"]
    total_by_slug = {}
    for p in persona:
        total_by_slug[p["slug"]] = p["exhibitor_count"] or scale.get(p["slug"])

    hits = match_reuse(persona, exhs)
    hit_slugs = {h["slug"] for h in hits}
    print("复用匹配：%d / %d 命中（%s）" % (
        len(hit_slugs), len(persona), ", ".join(sorted(hit_slugs)) or "-"))

    records: list[dict] = []
    for h in hits:
        cat = category.get(h["slug"])
        st = reuse_stats(mconn, h["exhibition_id"], cat)
        total = total_by_slug.get(h["slug"])
        comp = st["competitor_count"] if cat and st["labeled"] else None
        records.append({
            "slug": h["slug"], "source": "reuse_main",
            "listing_count": st["listing_count"],
            "has_industry": st["labeled"] > 0,
            "completeness": round(st["listing_count"] / total, 3) if total else None,
            "competitor_count_by_category": comp,
            "note": "复用 exhibitions#%d《%s》（%s，匹配键 %s）｜industry 有标注 %d/%d｜"
                    "该展展商总数 %s" % (
                        h["exhibition_id"], h["exhibition_title"], h["method"],
                        h["key_exhibition"][:24] or h["matched_on"],
                        st["labeled"], st["listing_count"],
                        ("%d" % total) if total else "未知"),
            "target_category": cat,
            "reuse_exhibition_id": h["exhibition_id"],
            "e2_ready": comp is not None,
        })

    # 未命中 → 爬
    pending = [p for p in persona if p["slug"] not in hit_slugs]
    if not args.reuse_only and pending:
        targets = pick_crawl_targets([p["slug"] for p in pending],
                                     min(args.max_sites, len(pending)), only)
        by_slug = {p["slug"]: p for p in persona}
        jobs = [{"slug": s, "url": url.get(s), "category": category.get(s),
                 "status": status.get(s)} for s in targets]
        print("爬取 %d 站（限 %d 站 / 每站 ≤%d 请求，并发 %d）" % (
            len(jobs), args.max_sites, MAX_REQ_PER_SITE, args.workers))
        got: list[dict] = []
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(crawl_one, j): j for j in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                r = fut.result()
                got.append(r)
                print("  [%2d/%2d] %-20s %-6s %s" % (
                    i, len(jobs), r["slug"], r["source"],
                    (r["note"] or "")[:70]))
        got.sort(key=lambda r: targets.index(r["slug"]))
        for r in got:
            total = total_by_slug.get(r["slug"])
            if r["listing_count"] and total:
                r["completeness"] = round(r["listing_count"] / total, 3)
            r["e2_ready"] = False
            records.append(r)
        print("爬取用时 %.1f 秒" % (time.time() - t0))

    order = {p["slug"]: i for i, p in enumerate(persona)}
    records.sort(key=lambda r: order[r["slug"]])

    # 未进入本次范围的展，显式留一条 none，保证 94 条齐全
    covered = {r["slug"] for r in records}
    for p in persona:
        if p["slug"] in covered:
            continue
        records.append({
            "slug": p["slug"], "source": "none", "listing_count": None,
            "has_industry": None, "completeness": None,
            "competitor_count_by_category": None,
            "note": "未纳入本次：名录关键词弱，按限流未爬（批次 3 只覆盖前 %d 站）" % args.max_sites,
            "target_category": category.get(p["slug"]), "has_listing_page": None, "e2_ready": False,
        })
    records.sort(key=lambda r: order[r["slug"]])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sample_total": len(persona),
        "source_dist": dict(Counter(r["source"] for r in records)),
        "has_listing": sum(1 for r in records if r["listing_count"]),
        "listing_page_exists": sum(1 for r in records if r.get("has_listing_page")),
        "has_industry_field": sum(1 for r in records if r["has_industry"]),
        "e2_ready": sum(1 for r in records if r["e2_ready"]),
        "listing_method": dict(Counter(r.get("listing_method") for r in records
                                       if r.get("listing_method"))),
        "robots_stats": dict(_ROBOTS.stats),
        "exhibitions_total": len(exhs),
        "note": "crawl 段按批次1名录关键词强弱取前 N 站，属乐观偏置，可得率是上界",
    }
    OUT_JSON.write_text(json.dumps({"summary": summary, "records": records},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n→ %s" % OUT_JSON)
    print("source:", summary["source_dist"], "| 有名录条数", summary["has_listing"],
          "| 名录页存在", summary["listing_page_exists"],
          "| 有品类字段", summary["has_industry_field"], "| E2 可算", summary["e2_ready"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
