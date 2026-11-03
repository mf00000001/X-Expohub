"""
批次 1：为已核实官网的展会采集 7 个骨架字段。

字段（对应 docs/展会画像-采集字段清单.md 的编号）：
    1  title        展会名称（官网自称）
    2  start_date   开展日
    2  end_date     闭幕日
    3  venue        展馆
    3  city         城市
    6  organizer    主办方
    7  edition      届次
    14 deadline     报名/展位截止日
    11 category     主品类 —— 不抓，直接用名单里的映射

设计约束：
  · 只抓首页。子页（关于/参展报名）留到确认首页填充率不够时再加，避免 3 倍请求量。
  · 每个字段独立记 method 与 evidence，抽不到就是 null，**不猜、不补默认值**。
    猜出来的日期比空值危险得多——E4 的门限判断直接建立在开展日上。
  · robots 复用 expo_scraper.RobotsCache（已按 RFC 9309 改），并注入绕代理的 opener。

用法：
    python scripts/persona/collect_skeleton.py                  # 全量
    python scripts/persona/collect_skeleton.py --limit 5        # 抽样
    python scripts/persona/collect_skeleton.py --only awe,gile  # 指定
"""

from __future__ import annotations

import argparse
import gzip
import html as html_mod
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / "data" / "expo_candidates_final.json"
OUT_DIR = ROOT / "data" / "batch1"
RAW_DIR = OUT_DIR / "raw"
SAVE_RAW = True

sys.path.insert(0, str(ROOT.parent / "scripts" / "scrape"))
from expo_scraper import RobotsCache, USER_AGENT  # noqa: E402

TIMEOUT = 15
MAX_BYTES = 600_000

# 国内站不能走本机系统代理（127.0.0.1:7891 会把它接走并回假错误）。
# 也不校验证书：多个展会站缺中间证书，浏览器能开但我们这里会报
# CERTIFICATE_VERIFY_FAILED，从而把"可访问"误判成"站点已死"。
# 这里只读公开页、不提交任何数据，放开证书校验不改变风险面。
_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=ssl._create_unverified_context()),
)
_ROBOTS = RobotsCache(timeout=15, opener=_OPENER)

# ---------------------------------------------------------------- 场馆 / 城市

VENUES = [
    ("国家会展中心（上海）", "上海", ["国家会展中心"]),
    ("上海新国际博览中心", "上海", ["新国际博览中心", "SNIEC"]),
    ("上海世博展览馆", "上海", ["世博展览馆"]),
    ("广交会展馆", "广州", ["广交会展馆", "中国进出口商品交易会展馆", "琶洲展馆"]),
    ("广州保利世贸博览馆", "广州", ["保利世贸博览馆"]),
    ("中国国际展览中心（顺义馆）", "北京", ["中国国际展览中心", "新国展"]),
    ("北京国家会议中心", "北京", ["国家会议中心"]),
    ("深圳国际会展中心", "深圳", ["深圳国际会展中心"]),
    ("深圳会展中心", "深圳", ["深圳会展中心"]),
    ("成都世纪城新国际会展中心", "成都", ["世纪城新国际会展中心", "成都世纪城"]),
    ("重庆国际博览中心", "重庆", ["重庆国际博览中心"]),
    ("杭州国际博览中心", "杭州", ["杭州国际博览中心"]),
    ("南京国际博览中心", "南京", ["南京国际博览中心"]),
    ("厦门国际会展中心", "厦门", ["厦门国际会展中心"]),
    ("青岛国际会展中心", "青岛", ["青岛国际会展中心"]),
    ("义乌国际博览中心", "义乌", ["义乌国际博览中心"]),
    ("广东现代国际展览中心", "东莞", ["广东现代国际展览中心", "厚街"]),
    ("中山古镇灯都会展中心", "中山", ["灯都会展中心", "古镇会展中心"]),
    ("永康国际会展中心", "永康", ["永康国际会展中心"]),
    ("晋江国际会展中心", "晋江", ["晋江国际会展中心"]),
    ("温州国际会展中心", "温州", ["温州国际会展中心"]),
    ("潭洲国际会展中心", "佛山", ["潭洲国际会展中心"]),
    ("宁波国际会展中心", "宁波", ["宁波国际会展中心"]),
    ("武汉国际博览中心", "武汉", ["武汉国际博览中心"]),
    ("郑州国际会展中心", "郑州", ["郑州国际会展中心"]),
    ("国家会展中心（天津）", "天津", ["国家会展中心（天津）", "梅江会展中心"]),
    ("山东国际会展中心", "济南", ["山东国际会展中心"]),
    ("太湖国际博览中心", "无锡", ["太湖国际博览中心"]),
    ("香港会议展览中心", "香港", ["香港会议展览中心", "HKCEC"]),
    ("亚洲国际博览馆", "香港", ["亚洲国际博览馆", "AsiaWorld"]),
    ("海南国际会展中心", "海口", ["海南国际会展中心"]),
    ("南宁国际会展中心", "南宁", ["南宁国际会展中心"]),
]
CITY_HINTS = ["上海", "北京", "广州", "深圳", "成都", "重庆", "杭州", "南京", "厦门",
              "青岛", "义乌", "东莞", "中山", "永康", "晋江", "温州", "佛山", "宁波",
              "武汉", "郑州", "天津", "济南", "无锡", "香港", "海口", "南宁", "苏州"]

MONTHS_EN = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _ok_date(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


# 连字符与间隔号的 Unicode 变体。页面里大量混用 hyphen / en dash / em dash /
# 全角减号 / 波浪号，以及"2027·4·13"这种间隔号写法。
# 不先归一化，正则就得为每种组合写一遍，而且永远漏。
_DASH = str.maketrans({c: "-" for c in "‐‑‒–—―−－~～"})
_DOT = str.maketrans({c: "." for c in "·・•"})
# 全角/半角括号混用是中文站的通病，同一个页面上两种写法并存（进博会就是如此）。
# 不归一化会让"依据逐字出现在正文里"这条判据在括号这里失效。
_PAREN = str.maketrans({"（": "(", "）": ")", "【": "[", "】": "]", "〔": "[", "〕": "]"})


def _norm_sep(s: str) -> str:
    return s.translate(_DASH).translate(_DOT).translate(_PAREN)


def extract_dates(text: str) -> tuple[str | None, str | None, str]:
    """返回 (start, end, evidence)。抽不到就是 None —— 宁可空着也不猜。"""
    t = _norm_sep(re.sub(r"\s+", " ", text))
    # 页面排版常把日期拆开写："2026. 7. 24 ~ 26"、"2027 年 3 月 17 日"。
    # 数字与日期分隔符之间的空格先吃掉，否则所有正则都要为空格留位。
    # 负向环视是必须的：英文月份缩写后面也跟句点（"Apr. 14"），
    # 那个句点属于缩写不属于日期，"Apr. 14" 若被压成 "Apr.14"，英文正则就失配了。
    t = re.sub(r"(?<![A-Za-z])\s*([./\-年月日])\s*(?=[\d])", r"\1", t)

    # 1) 中文：2027年3月17-20日 / 2026年11月10日至12日 / 2026年11月10日-11月12日
    m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*[-–—~至到]\s*"
                  r"(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*日", t)
    if m:
        y, m1, d1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
        m2 = int(m.group(4)) if m.group(4) else m1
        d2 = int(m.group(5))
        s = _ok_date(y, m1, d1)
        e = _ok_date(y, m2, d2)
        if s:
            return s, e or s, m.group(0)[:40]

    # 2) 中文跨年：2026年12月30日-2027年1月2日
    m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*[-–—~至到]\s*"
                  r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", t)
    if m:
        s = _ok_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        e = _ok_date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
        if s:
            return s, e or s, m.group(0)[:40]

    # 3) ISO / 点分：2026-11-10 ~ 2026-11-12 / 2026.11.10-12
    m = re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\s*[-–—~至到]\s*"
                  r"(?:(20\d{2})[-./])?(\d{1,2})[-./](\d{1,2})", t)
    if m:
        s = _ok_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        y2 = int(m.group(4)) if m.group(4) else int(m.group(1))
        e = _ok_date(y2, int(m.group(5)), int(m.group(6)))
        if s:
            return s, e or s, m.group(0)[:40]

    # 3b) 同年同月省略写法：2026.11.10-12 / 2026-11-10~12
    m = re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\s*[-–—~至到]\s*(\d{1,2})(?![\d])", t)
    if m:
        s = _ok_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        e = _ok_date(int(m.group(1)), int(m.group(2)), int(m.group(4)))
        if s:
            return s, e or s, m.group(0)[:40]

    # 4) 英文：March 17-20, 2027 / Nov 10 - 12, 2026
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})\s*[-–—]\s*(\d{1,2}),?\s*(20\d{2})", t)
    if m:
        mo = MONTHS_EN.get(m.group(1)[:3].lower())
        if mo:
            s = _ok_date(int(m.group(4)), mo, int(m.group(2)))
            e = _ok_date(int(m.group(4)), mo, int(m.group(3)))
            if s:
                return s, e or s, m.group(0)[:40]

    # 4b) 英文日在前：1-3 September 2027（cite 2027 这类国际站常见）
    m = re.search(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s*(20\d{2})", t)
    if m:
        mo = MONTHS_EN.get(m.group(3)[:3].lower())
        if mo:
            s = _ok_date(int(m.group(4)), mo, int(m.group(1)))
            e = _ok_date(int(m.group(4)), mo, int(m.group(2)))
            if s:
                return s, e or s, m.group(0)[:40]

    # 5) 只有单个日期：2027年3月17日
    m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", t)
    if m:
        s = _ok_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if s:
            return s, s, m.group(0)[:40]
    return None, None, ""


def extract_venue(text: str) -> tuple[str | None, str | None, str]:
    for name, city, keys in VENUES:
        for k in keys:
            if k in text:
                return name, city, k
    for c in CITY_HINTS:
        if c in text:
            return None, c, f"仅命中城市词 {c}"
    return None, None, ""


ORG_NOISE = ("微信", "公众号", "二维码", "微博", "网站", "电话", "邮箱", "扫码", "APP", "app",
             "下载中心", "新闻中心", "媒体中心", "服务中心", "帮助中心", "会员中心",
             "个人中心", "登录", "首页")
# 主办方必须是机构名。放宽后置语序后，"具有32年展会举办经验…主办"这类营销句会被误抽，
# 用它挡掉——宁可留空，也不要给下游一个看着像人名的字符串。
ORG_SUFFIX = ("协会", "学会", "委员会", "公司", "集团", "中心", "商会", "联合会",
              "基金会", "研究院", "研究所", "会展", "展览", "政府", "厅", "局", "部",
              "促进会", "工业联合会", "总会", "社", "组委会", "办公室", "办事处", "署", "大学", "学院")


def _looks_like_org(v: str) -> bool:
    """用'以机构后缀结尾'判定，而不是'包含'。

    包含判定会把 '名称、展品范围、展出时间、展览规模、可行性报告' 当成机构名
    （因为它含'展览'）。结尾判定能挡住这类列表碎片。
    """
    if not (3 <= len(v) <= 50):
        return False
    if any(n in v for n in ORG_NOISE):
        return False
    if "的" in v or v.startswith(("通过", "具有", "致力于", "旨在", "为", "有权", "发现")):
        return False
    tail = v.strip(" 　）)")
    return any(tail.endswith(s) for s in ORG_SUFFIX)


def extract_organizer(text: str) -> tuple[str | None, str]:
    # 语序一（前置）：主办单位：中国家用电器协会
    for pat in (r"主办单位\s*[:：]?\s*([^\n。；;|]{2,80})",
                r"主办方\s*[:：]?\s*([^\n。；;|]{2,80})",
                r"主办\s*[:：]\s*([^\n。；;|]{2,80})"):
        m = re.search(pat, text)
        if m:
            raw = m.group(1).strip(" 　,，、")
            # 同一行常把承办/协办连着写，主办方到第一个分隔词就结束
            v = re.split(r"承办|协办|支持|赞助|指导|主办", raw)[0].strip(" 　,，、：:")
            if _looks_like_org(v):
                return v, m.group(0)[:50]

    # 语序二（后置）：由中国对外贸易中心（集团）有限公司、中国建筑装饰协会主办
    m = re.search(r"(?:由)?([^，。；\n|]{2,60}(?:、[^，。；\n|]{2,60}){0,2})\s*(?:共同)?主办", text)
    if m:
        v = m.group(1).strip(" 　,，、：:由")
        # "本届展会由中国机床工具工业协会主办" → 去掉主语
        v = re.sub(r"^(本届|此次|本次|该)?(展会|展览会|博览会)?由?", "", v).strip(" 　,，、：:")
        if _looks_like_org(v):
            return v, m.group(0)[:50]
    return None, ""


_CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_to_int(s: str) -> int | None:
    """把'二十五''十五''五'转成整数。只处理到百位，展会届次够用。"""
    if s.isdigit():
        return int(s)
    if not s or any(ch not in _CN_DIGIT and ch not in "十百" for ch in s):
        return None
    total, unit = 0, 1
    if "百" in s:
        head, _, tail = s.partition("百")
        total += (_CN_DIGIT.get(head, 0) if head else 1) * 100
        s = tail
    if "十" in s:
        head, _, tail = s.partition("十")
        total += (_CN_DIGIT.get(head, 0) if head else 1) * 10
        s = tail
    for ch in s:
        if ch in _CN_DIGIT:
            total += _CN_DIGIT[ch]
    return total or None


def extract_edition(text: str, scope: str | None = None) -> tuple[int | None, str]:
    """届次。scope 把搜索范围收窄到标题+首屏。

    同一页常并排出现多个届次（子展、同期活动、往届回顾）。CMEF 实为第 90 余届，
    但页面里有"第七届XX论坛"，取第一个就会抽成 7。这里取**范围内最大**的那个：
    对同期子展/论坛，主展届次几乎总是最大。
    """
    hay = scope if scope is not None else text
    nums = [(_cn_to_int(m.group(1)), m.group(0))
            for m in re.finditer(r"第\s*([0-9]{1,3}|[零〇一二两三四五六七八九十百]{1,6})\s*届", hay)]
    nums = [(n, ev) for n, ev in nums if n and 1 <= n <= 200]
    if not nums:
        return None, ""
    n, ev = max(nums, key=lambda x: x[0])
    return n, ev


def classify_dates(start: str | None, end: str | None, today: date) -> tuple[str, str, int | None]:
    """返回 (status, note, typical_month)。

    status:
      current  —— 开展日在今天之后，可直接算 E4
      past     —— 开展日已过（含刚结束的），官网仍挂着
      none     —— 抽不到

    往届不丢：它至少能给出「这个展通常在几月办」这个真实信号，
    但绝不能拿去算「距开展天数」——那会得到负数，还会安静地流进下游。

    边界定在「今天」，不设 90 天宽限：开展日已过就意味着没法订展位了，
    哪怕只过了 3 天。宽限期会让"刚结束的展"继续冒充本届，
    下游一旦拿它当门限就会得出"还能去"的荒谬结论。
    """
    if not start:
        return "none", "未抽到日期", None
    try:
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end or start, "%Y-%m-%d").date()
    except ValueError:
        return "none", "格式异常", None
    if e < s or (e - s).days > 60:
        return "none", "展期不合理", None
    if s > date(today.year + 4, 12, 31):
        return "none", "日期超出合理范围", None
    if s < today:
        days_ago = (today - s).days
        if days_ago <= 90:
            return "past", f"开展日已过去 {days_ago} 天（已结束或正在举办）", s.month
        months_ago = (today.year - s.year) * 12 + (today.month - s.month)
        return "past", f"官网仍展示 {months_ago} 个月前的往届展期", s.month
    return "current", "", s.month


def dates_sane(start: str | None, end: str | None, today: date) -> tuple[bool, str]:
    """保留旧接口：仅判断是否可用于「倒计时」类计算（往届返回 False）。"""
    st, note, _ = classify_dates(start, end, today)
    return st == "current", note


def extract_deadline(text: str) -> tuple[str | None, str]:
    # 只认"截止/截稿/报名截止"邻近 40 字内的完整日期
    for m in re.finditer(r"(报名|展位|参展|申请)?[^。\n]{0,6}(截止|截至)[^。\n]{0,40}", text):
        seg = m.group(0)
        s, _, ev = extract_dates(seg)
        if s:
            return s, seg[:50]
    return None, ""


def extract_jsonld_event(html: str) -> dict:
    """schema.org Event 是最可靠来源，优先于正则。"""
    out: dict = {}
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip().rstrip(";"))
        except Exception:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if any(isinstance(t, str) and "Event" in t for t in types if t):
                loc = node.get("location")
                if isinstance(loc, list):
                    loc = loc[0] if loc else None
                if isinstance(loc, dict):
                    out.setdefault("venue", loc.get("name") or "")
                    addr = loc.get("address")
                    if isinstance(addr, dict):
                        out.setdefault("city", addr.get("addressLocality") or "")
                if node.get("startDate"):
                    out.setdefault("start", str(node["startDate"])[:10])
                if node.get("endDate"):
                    out.setdefault("end", str(node["endDate"])[:10])
                if node.get("name"):
                    out.setdefault("title", str(node["name"]).strip())
                org = node.get("organizer")
                if isinstance(org, dict) and org.get("name"):
                    out.setdefault("organizer", str(org["name"]).strip())
                elif isinstance(org, list) and org and isinstance(org[0], dict):
                    out.setdefault("organizer", str(org[0].get("name") or "").strip())
    return {k: v for k, v in out.items() if v}


# ---------------------------------------------------------------- 抓取

def _decode(raw: bytes, hint: str | None) -> str:
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


def fetch(url: str, timeout: int = TIMEOUT) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    })
    with _OPENER.open(req, timeout=timeout) as resp:
        raw = resp.read(MAX_BYTES * 8)
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        html = _decode(raw[:MAX_BYTES], resp.headers.get_content_charset())
        return resp.status, resp.geturl(), html


def visible_text(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    # 用 html.unescape 而不是手写替换表：页面里除 &nbsp; 之外还有大量数字实体，
    # 比如分隔号写成 &#183;（·）、&#8211;（–）。漏掉它们会让"依据逐字出现在正文里"
    # 这条判据失效——实测 b-furniture-wood 整条 6 个字段因此全被拦下。
    t = html_mod.unescape(t)
    return re.sub(r"[ \t\r\f\v]+", " ", t)


# 展期/场馆/主办方/截止日大多不在首页，而在"关于""参展"这类子页。
# 只跟同域链接，最多 2 个，避免把整站爬一遍。
LINK_HINTS = ("about", "exhibit", "参展", "关于", "概况", "简介", "介绍", "overview", "fair-info")
LINK_BLOCK = ("login", "register", "news", "新闻", "download", "下载", "video", "video",
              "member", "cart", "pay", ".pdf", ".jpg", ".png", "javascript:")


def pick_subpages(html: str, base_url: str, limit: int = 3) -> list[str]:
    """按**链接文字**挑子页，而不是按 URL 路径。

    很多站点（awe 的 SiteServer、各种 CMS）路径是 /contents/101/14166.html，
    路径里根本没有 about/exhibit 这类词，只能看 <a> 的文字。
    """
    host = urllib.parse.urlsplit(base_url).netloc
    scored: list[tuple[int, str, bool]] = []
    seen = {base_url.rstrip("/")}
    for m in re.finditer(r"""<a\b[^>]*href=["']([^"']{2,200})["'][^>]*>(.*?)</a>""",
                         html, re.I | re.S):
        href, inner = m.group(1), m.group(2)
        anchor = re.sub(r"<[^>]+>", "", inner)
        anchor = re.sub(r"\s+", "", anchor).lower()
        if not anchor:
            continue
        u = urllib.parse.urljoin(base_url, href).split("#")[0]
        if urllib.parse.urlsplit(u).netloc != host or u in seen:
            continue
        low = u.lower()
        if any(b in low for b in LINK_BLOCK):
            continue
        score = 0
        is_exhibit = any(k in anchor for k in ("参展", "展位", "报名", "exhibit", "booking"))
        if any(k in anchor for k in ("关于", "简介", "概况", "介绍", "overview", "about")):
            score += 10
        if is_exhibit:
            score += 10
        if any(k in anchor for k in ("展会", "展览", "fair", "show")):
            score += 3
        if score:
            seen.add(u)
            scored.append((score, u, is_exhibit))
    scored.sort(key=lambda x: -x[0])
    out: list[str] = []
    for _, u, _ in scored:
        if u not in out:
            out.append(u)
        if len(out) >= limit:
            break
    # 展会截止日几乎只在"参展/报名"页出现，保证这类页至少进一个
    if not any(x[2] for x in scored[:limit]):
        for _, u, ex in scored:
            if ex and u not in out:
                out[-1] = u
                break
    return out


def _fld(value, method: str, evidence: str, conf: str | None = None) -> dict:
    """字段值 + 来源 + 可信度。conf 不传时按 method 推断：
    jsonld/词典/配置 属高；正则属中；往届日期另行降为低。"""
    if conf is None:
        conf = "high" if method in ("jsonld", "dict", "config", "title_tag") else "medium"
    return {"value": value, "method": method, "evidence": evidence[:80], "conf": conf}


def collect_one(e: dict) -> dict:
    rec = {
        "id": e["id"], "layer": e["layer"], "category": e["category"],
        "name": e.get("official_name") or e["name"], "url": e.get("url"),
        "fields": {}, "error": None,
    }
    if not e.get("url"):
        rec["error"] = "no_url"
        return rec

    # 区分"对方明确不让"和"我们连不上"——后者重试后仍失败才放弃，不能混为一谈
    why = _ROBOTS.reason(e["url"])
    if why not in ("allow", "absent"):
        rec["error"] = "robots_denied" if why == "deny" else "robots_unreachable"
        rec["robots"] = why
        return rec

    try:
        status, final, html = fetch(e["url"])
    except Exception as ex:
        rec["error"] = f"{type(ex).__name__}: {str(ex)[:60]}"
        return rec

    # 跟进 1~2 个"关于/参展"子页：展期、场馆、主办方基本都在那里
    pages = [{"url": e["url"], "html": html}]
    for sub in pick_subpages(html, final):
        if not _ROBOTS.allowed(sub):
            continue
        try:
            _, f2, h2 = fetch(sub)
            pages.append({"url": sub, "html": h2})
            rec.setdefault("subpages", []).append(sub)
        except Exception:
            continue

    text = " ".join(visible_text(p["html"]) for p in pages)[:40000]
    html_all = " ".join(p["html"] for p in pages)
    ld = extract_jsonld_event(html_all)
    title_tag = ""
    mt = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if mt:
        title_tag = re.sub(r"\s+", " ", mt.group(1)).strip()

    F = rec["fields"]
    notes: list[str] = []
    today = date.today()

    # 名称
    if ld.get("title"):
        F["title"] = _fld(ld["title"], "jsonld", "schema.org Event.name")
    elif title_tag:
        F["title"] = _fld(title_tag, "title_tag", "<title>")

    # 日期（先 jsonld，再正则；两者都要过三态分类）
    cand_start, cand_end, cand_method, cand_ev = None, None, "", ""
    if ld.get("start"):
        cand_start, cand_end = ld["start"], ld.get("end") or ld["start"]
        cand_method, cand_ev = "jsonld", "Event.startDate"
    else:
        s, ed, ev = extract_dates(text)
        if s:
            cand_start, cand_end, cand_method, cand_ev = s, ed or s, "regex", ev

    status, why, typical_month = "none", "", None
    if cand_start:
        status, why, typical_month = classify_dates(cand_start, cand_end, today)
        if status == "current":
            F["start_date"] = _fld(cand_start, cand_method, cand_ev)
            F["end_date"] = _fld(cand_end or cand_start, cand_method, cand_ev)
        elif status == "past":
            # 往届不丢，但不叫 start_date —— 字段名必须让下游一眼看出它不能算倒计时。
            # 直接写 start_date 会让某个忘了看 dates_status 的调用方算出 -580 天。
            F["prev_start_date"] = _fld(cand_start, cand_method, cand_ev, conf="low")
            F["prev_end_date"] = _fld(cand_end or cand_start, cand_method, cand_ev, conf="low")
            notes.append("往届展期：%s ~ %s（%s）" % (cand_start, cand_end, why))
        else:
            notes.append("日期不可用（%s）：%s ~ %s" % (why, cand_start, cand_end))
    rec["dates_status"] = status
    rec["typical_month"] = typical_month

    # 场馆 / 城市
    v, c, ev = extract_venue(text)
    if ld.get("venue"):
        F["venue"] = _fld(ld["venue"], "jsonld", "Event.location.name")
    elif v:
        F["venue"] = _fld(v, "dict", ev)
    if ld.get("city"):
        F["city"] = _fld(ld["city"], "jsonld", "Event.location.address")
    elif c:
        F["city"] = _fld(c, "dict", ev)

    # 主办方
    if ld.get("organizer"):
        F["organizer"] = _fld(ld["organizer"], "jsonld", "Event.organizer.name")
    else:
        o, ev = extract_organizer(text)
        if o:
            F["organizer"] = _fld(o, "regex", ev)

    # 届次：搜索范围收窄到标题 + 首屏，避开页脚/子展的届次
    n, ev = extract_edition(text, scope=(title_tag + " " + text[:3000]))
    if n:
        F["edition"] = _fld(n, "regex", ev)

    # 截止日
    d, ev = extract_deadline(text)
    if d:
        ok, why = dates_sane(d, d, today)
        if ok:
            F["deadline"] = _fld(d, "regex", ev)
        else:
            notes.append("截止日不可用（%s）：%s" % (why, d))

    # 主品类来自名单，不是抓的
    F["category"] = _fld(e["category"], "config", "18 品类映射表")

    rec["final_url"] = final
    rec["http"] = status
    rec["robots"] = "allow"
    if notes:
        rec["notes"] = notes
    rec["filled"] = sum(1 for k in ("title", "start_date", "end_date", "venue", "city",
                                    "organizer", "edition", "deadline") if k in F)
    # 正文落盘：一旦有 LLM key，抽取可以离线重跑，不必重新爬一遍
    # （网站内容会变、robots 会变，而"这一天的页面长什么样"是不可再生的）
    if SAVE_RAW:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / f"{rec['id']}.txt").write_text(
            "URL: %s\nFINAL: %s\nTITLE_TAG: %s\nPAGES: %d\n%s\n%s" % (
                e["url"], final, title_tag, len(pages), "-" * 60, text),
            encoding="utf-8")
        rec["raw_chars"] = len(text)
    return rec


SKELETON_KEYS = ("title", "start_date", "end_date", "venue", "city", "organizer", "edition", "deadline")


def main() -> int:
    global SAVE_RAW
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-raw", action="store_true", help="不落盘正文")
    args = ap.parse_args()
    SAVE_RAW = not args.no_raw

    data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    expos = [e for e in data["expos"] if not e.get("duplicate_of")]
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        expos = [e for e in expos if e["id"] in want]
    if args.limit:
        expos = expos[: args.limit]

    print("采集 %d 个展会（已去重），并发 %d" % (len(expos), args.workers))
    results: list[dict] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(collect_one, e): e for e in expos}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            if r.get("error"):
                flag = "ERR "
            else:
                flag = "%d/8" % r.get("filled", 0)
            print("  [%3d/%3d] %-5s %-20s %s" % (
                i, len(expos), flag, r["id"], (r.get("fields", {}).get("start_date", {}) or {}).get("value")
                or r.get("error") or ""))

    order = {e["id"]: i for i, e in enumerate(expos)}
    results.sort(key=lambda x: order[x["id"]])

    # 统计
    ok = [r for r in results if not r.get("error")]
    fill = {k: sum(1 for r in ok if k in r["fields"]) for k in SKELETON_KEYS}
    by_method: dict[str, dict[str, int]] = {}
    for r in ok:
        for k in SKELETON_KEYS:
            if k in r["fields"]:
                m = r["fields"][k]["method"]
                by_method.setdefault(k, {}).setdefault(m, 0)
                by_method[k][m] += 1

    dates_dist: dict[str, int] = {"current": 0, "past": 0, "none": 0}
    for r in ok:
        dates_dist[r.get("dates_status", "none")] = dates_dist.get(r.get("dates_status", "none"), 0) + 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "ok": len(ok),
        "errors": {r["id"]: r["error"] for r in results if r.get("error")},
        "fill": fill,
        "fill_rate": {k: round(v / len(ok), 3) for k, v in fill.items()} if ok else {},
        "by_method": by_method,
        "dates_status": dates_dist,
        "prev_date_kept": sum(1 for r in ok if "prev_start_date" in r["fields"]),
        "typical_month_known": sum(1 for r in ok if r.get("typical_month")),
        "robots_stats": _ROBOTS.stats,
        "avg_filled": round(sum(r.get("filled", 0) for r in ok) / len(ok), 2) if ok else 0,
    }
    (OUT_DIR / "skeleton.json").write_text(
        json.dumps({"summary": summary, "records": results}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print("\n" + "=" * 70)
    print("采集完成，用时 %.1f 秒 ｜ 成功 %d / %d" % (time.time() - t0, len(ok), len(results)))
    print("=" * 70)
    print("字段填充率（分母 = 成功采集的 %d 个）" % len(ok))
    for k in SKELETON_KEYS:
        bar = "#" * int(40 * fill[k] / max(len(ok), 1))
        print("  %-12s %3d  %4.0f%%  %s" % (k, fill[k], 100 * fill[k] / max(len(ok), 1), bar))
    print()
    print("平均每展填出 %.2f / 8 个字段" % summary["avg_filled"])
    print("日期三态：本届 %d ｜ 往届 %d（已保留为 prev_start_date）｜ 无 %d" % (
        dates_dist["current"], dates_dist["past"], dates_dist["none"]))
    print("可推出「通常几月办」的展会：%d 个" % summary["typical_month_known"])
    print("robots: allow=%d deny=%d absent=%d error=%d" % (
        _ROBOTS.stats["allow"] + _ROBOTS.stats["absent"], _ROBOTS.stats["deny"],
        _ROBOTS.stats["absent"], _ROBOTS.stats["error"]))
    if summary["errors"]:
        print("\n失败 %d 个：%s" % (len(summary["errors"]), list(summary["errors"])[:8]))
    print("\n→ %s" % (OUT_DIR / "skeleton.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
