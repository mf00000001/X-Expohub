#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""公开名录导入器 + 脱敏（catalog_exhibitors / catalog_products）

背景
----
豆包爬取产物（目录里一堆 `payload_*.json`）需要灌进平台的两张公开名录表：

    catalog_exhibitors  UNIQUE(expo_name, name)
    catalog_products    UNIQUE(expo_name, exhibitor_name, name)

产物规则很脏：列名可能带多余空格、城市列里塞了展馆号（"6号馆"）甚至 "1"、
企业性质/规模整列都是 "0"、展品详情里带访客手机号/邮箱/微信号。
所以这个脚本干四件事：**动态取列 → 清洗 → 脱敏 → 幂等 upsert**。

为什么不走 FastAPI 接口
----------------------
导入是一次性离线作业，走接口会触发登录态/权限/校验链路，而且 3 万+ 行会拖死
worker。这里直接用标准库 sqlite3 写库（不 import app 任何模块，不会触发启动
生命周期），因此脚本可以独立运行、也可在迁移脚本之后立刻跑。

幂等
----
`INSERT ... ON CONFLICT(<唯一键>) DO UPDATE SET ...`（SQLite ≥ 3.24）。
同一批跑第二遍所有行都会落到 updated，绝不会重复插入。
脚本自己维护两个集合来给出准确的 inserted / updated / skipped 计数：
  - `existing_keys`：库里当前已存在的唯一键快照（开始前一次性 SELECT）
  - `seen_keys`    ：本轮已处理过的唯一键（跨文件去重，重复行记 skipped）

脱敏
----
只清 `description` / `main_business` / `detail_html` 三个自由文本字段，
命中片段整体替换为 `[联系方式已隐藏]`，并累计可核对的统计（行数 + 次数）。

用法
----
    # 0) 先建表（另一个脚本负责）
    python scripts/migrate_catalog_tables.py

    # 1) 预演：只解析+清洗+统计，不写库（只读打开数据库）
    python scripts/import_catalog.py --dry-run --limit 200

    # 2) 先小批量试写到一个临时库
    python scripts/import_catalog.py --db %TEMP%\\catalog_try.db --limit 200

    # 3) 正式全量（由负责人统一执行）
    python scripts/import_catalog.py

    # 4) 只导一边
    python scripts/import_catalog.py --only products
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from collections import Counter

# ---------------------------------------------------------------------------
# 一、常量
# ---------------------------------------------------------------------------

DEFAULT_SOURCE = r"C:\Users\niu25\Doubao\chats\2026-10-19\new-chat\crawler"
DEFAULT_DB_REL = os.path.join("expohub-backend", "expohub.db")
MIGRATE_HINT = "scripts/migrate_catalog_tables.py"

EXHIBITORS_TABLE = "catalog_exhibitors"
PRODUCTS_TABLE = "catalog_products"

# 目标表字段（字段名由建表脚本固定，顺序即写入顺序）
EXHIBITOR_TARGET_COLUMNS = (
    "name", "name_en", "expo_name", "exhibition_id", "industry", "city",
    "country", "booth_no", "company_type", "scale", "main_business",
    "website", "product_count", "description", "source",
)
PRODUCT_TARGET_COLUMNS = (
    "name", "category", "application", "price_spec", "image", "detail_html",
    "exhibitor_name", "exhibitor_id", "expo_name", "booth_no", "source",
)
EXHIBITOR_CONFLICT = ("expo_name", "name")
PRODUCT_CONFLICT = ("expo_name", "exhibitor_name", "name")

# 目标字段 → 源列名候选。取列时先做「去空格归一后相等」，再退化到「列名包含」，
# 所以源表多加括号/备注（例如「展商名称（中文）」）也能命中。
EXHIBITOR_SOURCE_ALIASES = {
    "name": ("展商名称", "展商名", "企业名称", "公司名称"),
    "name_en": ("展商英文名", "英文名", "英文名称"),
    "expo_name": ("展会名称", "展会"),
    "industry": ("行业类别", "行业"),
    "country": ("国家/地区", "国家地区", "国家"),
    "company_type": ("企业性质", "企业类型"),
    "scale": ("企业规模", "规模"),
    "main_business": ("主营/经营范围", "主营业务", "经营范围"),
    "website": ("官网", "网址", "官网地址"),
    "product_count": ("展品数量",),
    "source": ("数据来源", "来源"),
    "description": ("展商简介", "公司简介", "企业简介", "简介"),
    "booth_no": ("展位号",),
    # 诊断用：这一列脏值很多（"1" / "6号馆" / "广东 深圳"），不写进 city
    "prov_city_raw": ("省份/城市", "省份城市", "省市"),
}
PRODUCT_SOURCE_ALIASES = {
    "expo_name": ("展会名称", "展会"),
    "platform": ("平台", "平台/主办方"),
    "booth_no": ("展位号",),
    "exhibitor_name": ("展商名称", "展商名"),
    "name": ("展品名称", "展品名", "产品名称"),
    "category": ("展品分类/参数", "展品分类", "分类"),
    "application": ("应用领域/用途", "应用领域", "用途"),
    "price_spec": ("价格/规格", "价格", "规格"),
    "detail_html": ("展品详情", "详情"),
    "source": ("数据来源", "来源"),
}

# 自动发现的文件名模式（4 种，前两种是展商，后两种是展品）
FILE_PATTERNS = {
    "exhibitors": ("payload_exhib_*", "payload_展商总表*"),
    "products": ("payload_prod_*", "payload_展品总表*"),
}

DETAIL_HTML_LIMIT = 8000  # 展品详情保留上限（字符）
PII_MASK = "[联系方式已隐藏]"
EXPO_REPORT_LIMIT = 25  # 展会关联报告最多打印多少个源展会名

# 视为「没有值」的占位符（分字段定义，避免误伤正常文本）
NULL_COUNTRY = frozenset({"", "0", "1"})
NULL_SCALE = frozenset({"", "0"})          # 规模整列 "0" 视为空
NULL_COMPANY_TYPE = frozenset({"", "0"})   # 企业性质整列 "0" 视为空
WEBSITE_PLACEHOLDERS = frozenset({"", "0", "无", "暂无", "-", "--", "/", "#", "空", "null", "none"})

# ---------------------------------------------------------------------------
# 二、清洗正则 / 规则
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_BOM = "\ufeff"

# 脱敏规则：顺序有意义 —— 先整段处理「联系人」，再处理号码类，
# 避免 "联系人：张三 13800000000" 只把手机号抠掉留下姓名。
#
# 手机号 / 座机额外加了「前后不紧邻数字」的边界（(?<!\d) / (?!\d)）：
# 不加的话，`0\d{2,3}-?\d{7,8}` 会把统一社会信用代码
# "91441900314863714L" 里的 "00314863714" 当成座机，把企业信用代码打残。
# 手机号顺带支持 "+86" / "86" 前缀，避免带国码的号码漏脱敏。
PII_RULES = (
    # 联系人：后面的内容（到空白为止）
    ("联系人", re.compile(r"联系人[:：]\s*\S*")),
    # 微信 / 微信号
    ("微信", re.compile(r"微信(?:号)?[:：]?\s*\S+")),
    # QQ / QQ号
    ("QQ", re.compile(r"QQ(?:号)?[:：]?\s*\d{5,}", re.I)),
    # 邮箱
    ("邮箱", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    # 手机号（可带 +86 / 86 前缀）
    ("手机号", re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")),
    # 座机（区号 3~4 位，可带连字符）
    ("座机", re.compile(r"(?<!\d)0\d{2,3}-?\d{7,8}(?!\d)")),
)
PII_TYPES = tuple(k for k, _ in PII_RULES)

# 城市推导：CMES 华机展的城市在竖线后缀里（"CMES华机展|佛山"）
CMES_RE = re.compile(r"CMES\s*华机展\s*[|｜]\s*([^|｜（(]*)")
# CMES 后缀白名单（拦住 "CMES华机展|" 这种空后缀和 "往届" 这类非城市词）
CMES_CITIES = (
    "东莞", "上海", "苏州", "宁波", "天津", "佛山", "西安", "青岛", "重庆",
    "济南", "郑州", "成都", "武汉", "合肥", "长沙", "南京", "杭州", "温州",
    "台州", "玉环", "厦门", "福州", "无锡", "常州", "嘉兴", "绍兴",
)

# 品牌展会 → 城市（第三个元素是「必须同时出现」的附加正则，None 表示无要求）
CITY_RULES = (
    (re.compile(r"高交会|CHTF", re.I), "深圳", None),
    (re.compile(r"CIOE|光电博览会", re.I), "深圳", None),
    (re.compile(r"CMEF", re.I), "北京", re.compile(r"北京")),
    (re.compile(r"NHNE", re.I), "北京", re.compile(r"北京")),
    (re.compile(r"玉环机床展"), "玉环", None),
    (re.compile(r"TME", re.I), "台州", None),
    (re.compile(r"台州机床展"), "台州", None),
)

# 展会品牌词（用于 exhibitions 标题关联的兜底匹配）
BRAND_RULES = (
    (re.compile(r"华机展|CMES", re.I), "华机展"),
    (re.compile(r"CMEF", re.I), "CMEF"),
    (re.compile(r"NHNE", re.I), "NHNE"),
    (re.compile(r"CIOE", re.I), "CIOE"),
    (re.compile(r"高交会|CHTF", re.I), "高交会"),
    (re.compile(r"玉环", re.I), "玉环"),
    (re.compile(r"台州机床展|TME", re.I), "台州"),
)

# 「历史各届汇总名录」这类桶不是某一届展会，默认不按品牌词强行挂接到某一届
HISTORY_BUCKET_RE = re.compile(r"历史|往届|累积|各届|汇总|名录")

# 展品详情里取第一张图
IMG_SRC_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.I
)
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.I | re.S)
_SCRIPT_TAIL_RE = re.compile(r"<script\b[^>]*>.*\Z", re.I | re.S)
_SCRIPT_SELF_RE = re.compile(r"<script\b[^>]*/\s*>", re.I)

_DOMAIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,}(?:[/?#].*)?$")

# ---------------------------------------------------------------------------
# 三、通用小工具
# ---------------------------------------------------------------------------


def harden_stdout() -> None:
    """重定向输出时强制 UTF-8，避免 Windows 控制台 cp936 把中文打成乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def hr(char: str = "-", width: int = 84) -> None:
    print(char * width)


def display_width(text: str) -> int:
    """终端显示宽度：中日韩全角字符按 2 列算，保证中文表格对齐。"""
    return sum(
        2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in str(text)
    )


def _pad(text, width: int) -> str:
    """左对齐补空格（按显示宽度）。"""
    text = str(text)
    return text + " " * max(0, width - display_width(text))


def _pad_l(value, width: int) -> str:
    """右对齐补空格（按显示宽度）。"""
    text = str(value)
    return " " * max(0, width - display_width(text)) + text


def norm_header(text) -> str:
    """列名归一：去 BOM、去所有空白（含全角空格、换行、制表符）。"""
    s = "" if text is None else str(text)
    s = s.replace(_BOM, "").replace("\u3000", " ")
    return _WS_RE.sub("", s)


def norm_key(text) -> str:
    """展会名归一（用于 exhibitions 关联）：
    去所有空白 + 分隔符统一（`|` `｜` `·` `•` `/` `／` 都当 `|`）。
    这样 "CMES华机展|佛山" 与 "CMES 华机展 · 佛山" 可以判等。
    """
    s = norm_header(text)
    for sep in ("｜", "·", "•", "／", "/"):
        s = s.replace(sep, "|")
    return s


def clean_plain(value) -> str:
    """普通文本字段清洗：None→""、全角空格/NBSP→空格、折叠连续空白、去首尾。"""
    if value is None:
        return ""
    s = str(value).replace("\u3000", " ").replace("\xa0", " ")
    return _WS_RE.sub(" ", s).strip()


def clean_text(value, max_len: int | None = None) -> str:
    s = clean_plain(value)
    if max_len is not None and len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def clean_optional(value, null_tokens) -> str:
    """可选字段：命中占位/非法值集合就置空。"""
    s = clean_plain(value)
    if s in null_tokens:
        return ""
    return s


def parse_int(value) -> int:
    """转 int；非法值一律 0（负数也按 0，名录里展品数量不可能是负的）。"""
    s = clean_plain(value).replace(",", "").replace("，", "")
    if not s:
        return 0
    if re.fullmatch(r"[+-]?\d+", s):
        n = int(s)
    else:
        try:
            f = float(s)
        except ValueError:
            return 0
        if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
            return 0
        n = int(f)
    return n if n > 0 else 0


def clean_website(value) -> str:
    """官网清洗：占位符置空；域名补 https://；明显不是网址的丢掉。"""
    s = clean_plain(value)
    if s.lower() in WEBSITE_PLACEHOLDERS:
        return ""
    if s.lower().startswith(("http://", "https://")):
        return s
    if s.startswith("//"):
        return "https:" + s
    if _DOMAIN_RE.match(s):
        return "https://" + s
    return ""  # 例如 "19.1.10"、"见名片"


def derive_city(expo_name: str) -> str:
    """从「展会名称」推城市。推不出就返回 ""。

    注意：源数据的 `省份/城市` 列不可信（"1"、"6号馆"、"广东 深圳" 混着），
    所以城市只认展会名称，不去读那一列。
    """
    name = clean_plain(expo_name)
    if not name:
        return ""
    m = CMES_RE.search(name)
    if m:
        token = m.group(1).strip()
        for city in CMES_CITIES:
            if token.startswith(city):
                return city
        return ""  # "CMES华机展|" / "CMES华机展|（待定）" → 留空
    for pattern, city, also in CITY_RULES:
        if pattern.search(name) and (also is None or also.search(name)):
            return city
    return ""


def brand_of(expo_name: str) -> str:
    """取展会品牌词，用于 exhibitions 标题兜底匹配。"""
    name = clean_plain(expo_name)
    for pattern, brand in BRAND_RULES:
        if pattern.search(name):
            return brand
    return ""


def strip_script(html: str) -> str:
    """去掉 <script>/<style> 块（含未闭合的尾巴）。"""
    if not html:
        return ""
    out = _SCRIPT_SELF_RE.sub("", html)
    out = _SCRIPT_RE.sub("", out)
    out = _SCRIPT_TAIL_RE.sub("", out)
    out = re.sub(r"<style\b[^>]*>.*?</style\s*>", "", out, flags=re.I | re.S)
    return out


def extract_first_image(html: str) -> str:
    """取展品详情里第一张 <img src>；`//img...` 补成 `https://img...`。"""
    if not html:
        return ""
    m = IMG_SRC_RE.search(html)
    if not m:
        return ""
    src = (m.group(1) or m.group(2) or m.group(3) or "").strip()
    if not src or src.lower().startswith("data:"):
        return ""
    if src.startswith("//"):
        return "https:" + src
    if src.lower().startswith(("http://", "https://")):
        return src
    if src.startswith("/"):
        return "https://img.expocme.cn" + src
    return "https://" + src


def truncate_html(html: str, limit: int = DETAIL_HTML_LIMIT) -> tuple[str, bool]:
    """按字符数截断 HTML，优先在标签边界切，避免留下半个标签。"""
    if len(html) <= limit:
        return html, False
    cut = html.rfind(">", 0, limit)
    if cut < int(limit * 0.6):  # 找不到合适边界就硬截
        return html[:limit], True
    return html[: cut + 1], True


# ---------------------------------------------------------------------------
# 四、脱敏器
# ---------------------------------------------------------------------------


class Sanitizer:
    """对自由文本字段做正则脱敏，并累计可核对的统计。"""

    def __init__(self, label: str):
        self.label = label
        self.rows_scanned = 0            # 扫描行数（进入脱敏环节的记录数）
        self.type_rows = Counter()       # 类型 → 命中行数（一行算一次）
        self.type_hits = Counter()       # 类型 → 命中次数（同一行两次算两次）
        self.field_rows = Counter()      # 字段 → 命中行数
        self.field_type_rows = Counter()  # (字段, 类型) → 命中行数
        self.rows_masked = 0             # 至少命中一种类型的行数

    def clean_record(self, record: dict, fields) -> dict:
        """对 record 中指定字段就地脱敏，返回新 dict（原 dict 不改）。"""
        self.rows_scanned += 1
        out = dict(record)
        row_types: set = set()
        for field in fields:
            text = out.get(field)
            if not text:
                continue
            masked, hits = self._mask(str(text))
            if not hits:
                continue
            out[field] = masked
            self.field_rows[field] += 1
            for pii_type, count in Counter(hits).items():
                row_types.add(pii_type)
                self.type_hits[pii_type] += count              # 次数：同一行命中两次算两次
                self.field_type_rows[(field, pii_type)] += count
        if row_types:
            self.rows_masked += 1
            for pii_type in row_types:
                self.type_rows[pii_type] += 1                   # 行数：一行算一次
        return out

    @staticmethod
    def _mask(text: str) -> tuple[str, list[str]]:
        """返回 (脱敏后的文本, 命中的类型列表[按出现次数重复])。"""
        hits: list[str] = []
        for pii_type, pattern in PII_RULES:
            text, count = pattern.subn(PII_MASK, text)
            if count:
                hits.extend([pii_type] * count)
        return text, hits

    def report(self) -> None:
        print(f"  [{self.label}] 扫描行数 {self.rows_scanned:,}，"
              f"命中并脱敏的行数 {self.rows_masked:,}")
        if not self.rows_scanned:
            return
        print("    " + _pad("类型", 10) + _pad_l("命中行数", 10) + _pad_l("命中次数", 10))
        for pii_type in PII_TYPES:
            print("    " + _pad(pii_type, 10)
                  + _pad_l(self.type_rows.get(pii_type, 0), 10)
                  + _pad_l(self.type_hits.get(pii_type, 0), 10))
        print("    " + _pad("合计", 10)
              + _pad_l(sum(self.type_rows.values()), 10)
              + _pad_l(sum(self.type_hits.values()), 10))
        if self.field_rows:
            print("    按字段分布（行数 / 次数）：")
            for field, rows in self.field_rows.most_common():
                detail = "、".join(
                    f"{t} {c} 次" for (f, t), c in self.field_type_rows.items() if f == field
                )
                print(f"      {field}: {rows} 行 → {detail}")

    def as_dict(self) -> dict:
        """导出统计（便于其他脚本复用/落盘）。"""
        return {
            "label": self.label,
            "rows_scanned": self.rows_scanned,
            "rows_masked": self.rows_masked,
            "type_rows": dict(self.type_rows),
            "type_hits": dict(self.type_hits),
        }


# ---------------------------------------------------------------------------
# 五、源文件发现 + 动态取列
# ---------------------------------------------------------------------------


def discover_files(source: str) -> dict:
    """按 4 种模式发现文件，返回 {kind: [(pattern, [files...]), ...]}。"""
    found = {}
    for kind, patterns in FILE_PATTERNS.items():
        groups = []
        for pattern in patterns:
            paths = sorted(
                p for p in glob.glob(os.path.join(source, pattern)) if os.path.isfile(p)
            )
            groups.append((pattern, paths))
        found[kind] = groups
    return found


def resolve_columns(index: dict, aliases: dict) -> dict:
    """把「目标字段 → 源列候选」解析成「目标字段 → 列下标」。

    先精确（去空格归一后相等），再退化到包含式匹配，最后放弃（None）。
    """
    resolved: dict[str, int | None] = {}
    for field, names in aliases.items():
        hit = None
        for name in names:
            key = norm_header(name)
            if key and key in index:
                hit = index[key]
                break
        if hit is None:
            for name in names:
                key = norm_header(name)
                if not key:
                    continue
                for col_key, col_idx in index.items():
                    if key in col_key:
                        hit = col_idx
                        break
                if hit is not None:
                    break
        resolved[field] = hit
    return resolved


def build_index(columns) -> dict:
    index: dict[str, int] = {}
    for i, name in enumerate(columns or []):
        key = norm_header(name)
        if key and key not in index:  # 同名列取第一个
            index[key] = i
    return index


def pick(row, col) -> str:
    """按下标取值；越界/None 安全返回 ""。"""
    if col is None or col >= len(row):
        return ""
    value = row[col]
    return "" if value is None else str(value)


def iter_source_records(files, aliases, kind_label: str):
    """流式产出 (源文件名, {目标字段: 原始值})。按 sheets[].columns 动态取列。"""
    for path in files:
        payload = load_payload(path, kind_label)
        if payload is None:
            continue
        sheets = payload.get("sheets") if isinstance(payload, dict) else None
        if not sheets and isinstance(payload, list):
            # 容错：直接是 [ {...}, {...} ] 的产物
            if payload and isinstance(payload[0], dict):
                columns = list(payload[0].keys())
                sheets = [{
                    "name": "data",
                    "columns": columns,
                    "data": [[item.get(c) for c in columns] for item in payload],
                }]
        for sheet in sheets or []:
            columns = sheet.get("columns") or []
            rows = sheet.get("data") or []
            if not columns:
                print(f"[warn] {os.path.basename(path)} sheet={sheet.get('name')!r} 没有 columns，跳过",
                      file=sys.stderr)
                continue
            resolved = resolve_columns(build_index(columns), aliases)
            if all(v is None for v in resolved.values()):
                print(f"[warn] {os.path.basename(path)} sheet={sheet.get('name')!r} 列名全不识别，跳过",
                      file=sys.stderr)
                continue
            for row in rows:
                if not isinstance(row, (list, tuple)):
                    continue
                yield path, {field: pick(row, col) for field, col in resolved.items()}


def load_payload(path: str, kind_label: str):
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            with open(path, "r", encoding=encoding) as fh:
                return json.load(fh)
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as exc:
            print(f"[warn] {kind_label} 文件解析失败，跳过：{path}（{exc}）", file=sys.stderr)
            return None
        except OSError as exc:
            print(f"[warn] {kind_label} 文件读取失败，跳过：{path}（{exc}）", file=sys.stderr)
            return None
    print(f"[warn] {kind_label} 文件编码无法识别，跳过：{path}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# 六、数据库
# ---------------------------------------------------------------------------


def resolve_db_path(arg_value: str | None) -> str:
    """--db 默认值解析：先看 CWD 下的 expohub-backend/expohub.db，
    再退到脚本所在目录的上一级（即 backend/expohub.db）。"""
    if arg_value:
        return os.path.abspath(arg_value)
    cwd_candidate = os.path.abspath(DEFAULT_DB_REL)
    if os.path.isfile(cwd_candidate):
        return cwd_candidate
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(backend_dir, "expohub.db")


def open_db(path: str, readonly: bool) -> sqlite3.Connection:
    """打开数据库。readonly=True 时用 `mode=ro` URI，从连接层面保证 dry-run 不写盘。"""
    if readonly:
        from urllib.parse import quote

        uri = "file:" + quote(path.replace("\\", "/"), safe="/:")
        conn = sqlite3.connect(uri, uri=True, timeout=10)
    else:
        conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")  # 后端可能在跑，别一撞锁就失败
    return conn


def table_columns(conn: sqlite3.Connection | None, table: str) -> list[str]:
    if conn is None:  # dry-run 且数据库不存在时，连接为空
        return []
    try:
        return [str(r[1]) for r in conn.execute(f'PRAGMA table_info("{table}")')]
    except sqlite3.DatabaseError:
        return []


def ensure_table(conn, table: str, needed, kind_label: str) -> bool:
    """表/字段体检。缺失时给出明确报错并提示先跑迁移脚本。"""
    columns = table_columns(conn, table)
    if not columns:
        print(f"[ERROR] 目标表 `{table}` 不存在，无法导入{kind_label}。", file=sys.stderr)
        print(f"        请先执行：python {MIGRATE_HINT}", file=sys.stderr)
        return False
    missing = [c for c in needed if c not in columns]
    if missing:
        print(f"[ERROR] 目标表 `{table}` 缺少字段：{', '.join(missing)}", file=sys.stderr)
        print(f"        表结构与脚本约定不一致，请先执行：python {MIGRATE_HINT}", file=sys.stderr)
        return False
    return True


def build_upsert_sql(table: str, columns, conflict, extra_update=()) -> str:
    col_list = ", ".join('"%s"' % c for c in columns)
    holders = ", ".join("?" * len(columns))
    sets = ['"%s" = excluded."%s"' % (c, c) for c in columns if c not in conflict]
    sets.extend(extra_update)
    conflict_list = ", ".join('"%s"' % c for c in conflict)
    return (
        f'INSERT INTO "{table}" ({col_list}) VALUES ({holders}) '
        f'ON CONFLICT({conflict_list}) DO UPDATE SET {", ".join(sets)}'
    )


def load_existing_keys(conn, table: str, conflict) -> set:
    try:
        rows = conn.execute(
            'SELECT %s FROM "%s"' % (", ".join('"%s"' % c for c in conflict), table)
        ).fetchall()
    except sqlite3.DatabaseError:
        return set()
    return {tuple("" if v is None else str(v) for v in row) for row in rows}


# ---------------------------------------------------------------------------
# 七、exhibitions 关联
# ---------------------------------------------------------------------------

MATCH_L1 = "L1-去空格/分隔符后相等"
MATCH_L2 = "L2-标题互为包含"
MATCH_L3 = "L3-品牌词+城市"
MATCH_L4 = "L4-品牌词唯一命中"
MATCH_NONE = "未匹配"
MATCH_AMBIGUOUS = "多候选择空"
MATCH_HISTORY = "历史汇总名录不挂接"


class ExpoMatcher:
    """把源数据的 expo_name 挂到平台已有 exhibitions.id 上。

    分层匹配（逐层降级，命中即返回）：
      L1 标题与展会名去空格/分隔符归一后完全相等
      L2 二者互为包含（长度 ≥ 6 才算，避免 "高交会" 这种短词乱挂）
      L3 品牌词 + 城市同时出现在标题里（"华机展"+"佛山" → CMES 华机展 · 佛山）
      L4 品牌词在标题里唯一出现（仅当 exhibition 表里只有一个候选）
    历史/往届汇总名录默认不参与 L4，避免把 1 万多行"历史各届"挂到某一届上。
    """

    def __init__(self, exhibitions, allow_history: bool = False):
        self.entries = [
            (int(eid), str(title), norm_key(title)) for eid, title in exhibitions
        ]
        self.allow_history = allow_history
        self.cache: dict[str, tuple[int | None, str, str]] = {}

    def match(self, expo_name: str, city: str) -> tuple[int | None, str, str]:
        """返回 (exhibition_id 或 None, 命中规则, 命中的标题)。结果按展会名缓存。"""
        key = norm_key(expo_name)
        result = self.cache.get(key)
        if result is None:
            result = self._match(expo_name, city, key)
            self.cache[key] = result
        return result

    def _match(self, expo_name, city, key):
        if not key:
            return None, MATCH_NONE, ""
        # L1 完全相等
        for eid, title, tkey in self.entries:
            if tkey == key:
                return eid, MATCH_L1, title
        # L2 互为包含
        if len(key) >= 6:
            cands = [
                (eid, title) for eid, title, tkey in self.entries
                if len(tkey) >= 6 and (tkey in key or key in tkey)
            ]
            if len(cands) == 1:
                return cands[0][0], MATCH_L2, cands[0][1]
            if len(cands) > 1:
                return None, MATCH_AMBIGUOUS, "; ".join(t for _, t in cands[:3])
        # L3 品牌词 + 城市
        brand = brand_of(expo_name)
        if brand and city:
            cands = [
                (eid, title) for eid, title, _ in self.entries
                if brand in title and city in title
            ]
            if len(cands) == 1:
                return cands[0][0], MATCH_L3, cands[0][1]
        # L4 品牌词唯一
        if brand:
            if HISTORY_BUCKET_RE.search(clean_plain(expo_name)) and not self.allow_history:
                return None, MATCH_HISTORY, ""
            cands = [(eid, title) for eid, title, _ in self.entries if brand in title]
            if len(cands) == 1:
                return cands[0][0], MATCH_L4, cands[0][1]
            if len(cands) > 1:
                return None, MATCH_AMBIGUOUS, f"{len(cands)} 个候选含品牌词 {brand!r}"
        return None, MATCH_NONE, ""


def load_exhibitions(conn) -> list:
    if not table_columns(conn, "exhibitions"):
        return []
    try:
        return conn.execute("SELECT id, title FROM exhibitions ORDER BY id").fetchall()
    except sqlite3.DatabaseError as exc:
        print(f"[warn] 读取 exhibitions 失败（{exc}），本次不做展会关联", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# 八、记录清洗
# ---------------------------------------------------------------------------


def clean_exhibitor_row(raw: dict, matcher: ExpoMatcher | None) -> dict:
    """展商记录 → 目标字段 dict（只做清洗，脱敏留给调用方在去重之后做）。"""
    expo_name = clean_text(raw.get("expo_name"))
    name = clean_text(raw.get("name"))
    city = derive_city(expo_name)
    exhibition_id = None
    if matcher is not None:
        exhibition_id = matcher.match(expo_name, city)[0]
    return {
        "name": name,
        "name_en": clean_text(raw.get("name_en")),
        "expo_name": expo_name,
        "exhibition_id": exhibition_id,
        "industry": clean_text(raw.get("industry")),
        "city": city,
        "country": clean_optional(raw.get("country"), NULL_COUNTRY),
        "booth_no": clean_text(raw.get("booth_no")),
        "company_type": clean_optional(raw.get("company_type"), NULL_COMPANY_TYPE),
        "scale": clean_optional(raw.get("scale"), NULL_SCALE),
        "main_business": clean_text(raw.get("main_business")),
        "website": clean_website(raw.get("website")),
        "product_count": parse_int(raw.get("product_count")),
        "description": clean_text(raw.get("description")),
        "source": clean_text(raw.get("source")),
    }


EXHIBITOR_PII_FIELDS = ("description", "main_business")
PRODUCT_PII_FIELDS = ("detail_html",)


def clean_product_row(
    raw: dict,
    exhibitor_ids: dict,
    known_exhibitor_keys: set,
) -> tuple[dict, bool]:
    """展品记录 → 目标字段 dict。返回 (record, 展商是否可关联)。

    脱敏 / 截断由调用方在去重之后做（保证脱敏统计只算真正入库的行）。
    """
    expo_name = clean_text(raw.get("expo_name"))
    exhibitor_name = clean_text(raw.get("exhibitor_name"))
    name = clean_text(raw.get("name"))
    detail_html = strip_script(str(raw.get("detail_html") or ""))
    record = {
        "name": name,
        "category": clean_text(raw.get("category")),
        "application": clean_text(raw.get("application")),
        "price_spec": clean_text(raw.get("price_spec")),
        "image": extract_first_image(detail_html),
        "detail_html": detail_html,
        "exhibitor_name": exhibitor_name,
        "exhibitor_id": exhibitor_ids.get((expo_name, exhibitor_name)),
        "expo_name": expo_name,
        "booth_no": clean_text(raw.get("booth_no")),
        "source": clean_text(raw.get("source")),
    }
    linkable = (expo_name, exhibitor_name) in known_exhibitor_keys
    return record, linkable


def finalize_product_record(record: dict, sanitizer: Sanitizer) -> dict:
    """展品入库前的最后两步：先脱敏、再按 8000 字符截断详情。

    顺序不能反：先截断会把 "1380000" 这种半个号码留在末尾，脱敏正则认不出来。
    """
    record = sanitizer.clean_record(record, PRODUCT_PII_FIELDS)
    record["detail_html"], _truncated = truncate_html(record["detail_html"], DETAIL_HTML_LIMIT)
    return record


# ---------------------------------------------------------------------------
# 九、写库
# ---------------------------------------------------------------------------


class TableWriter:
    """分批 upsert，并按唯一键精确区分 inserted / updated。"""

    def __init__(self, conn, table, columns, conflict, existing_keys, batch):
        self.conn = conn
        self.table = table
        self.columns = columns
        self.conflict = conflict
        self.batch = max(1, int(batch))
        self.existing_keys = existing_keys
        self.seen_keys: set = set()
        self.pending: list[tuple] = []
        actual = table_columns(conn, table)
        extra = ('"updated_at" = CURRENT_TIMESTAMP',) if "updated_at" in actual else ()
        self.sql = build_upsert_sql(table, columns, conflict, extra)
        self.inserted = 0
        self.updated = 0
        self.skipped_dup = 0
        self.skipped_empty = 0
        self.written = 0

    def key_of(self, record: dict):
        """取唯一键；主键缺失返回 None（这类行会被 skipped_empty 计掉）。"""
        key = tuple(str(record.get(c) or "") for c in self.conflict)
        if not key[0] or not record.get("name"):
            return None
        return key

    def is_duplicate(self, key) -> bool:
        return key in self.seen_keys

    def add(self, record: dict) -> str:
        """登记一行；返回 "inserted" / "updated" / "skipped"（调用方按需计数）。"""
        key = self.key_of(record)
        if key is None:
            self.skipped_empty += 1
            return "skipped"
        if key in self.seen_keys:
            self.skipped_dup += 1
            return "skipped"
        self.seen_keys.add(key)
        if key in self.existing_keys:
            self.updated += 1
            outcome = "updated"
        else:
            self.inserted += 1
            self.existing_keys.add(key)
            outcome = "inserted"
        self.pending.append(tuple(record.get(c) for c in self.columns))
        if len(self.pending) >= self.batch:
            self.flush()
        return outcome

    def flush(self) -> None:
        if not self.pending:
            return
        try:
            self.conn.executemany(self.sql, self.pending)
            self.conn.commit()
        except sqlite3.OperationalError as exc:
            self.conn.rollback()
            if "ON CONFLICT" in str(exc).upper():
                raise SystemExit(
                    f"[ERROR] `{self.table}` 上没有与 "
                    f"({', '.join(self.conflict)}) 匹配的唯一约束：{exc}\n"
                    f"        请先执行：python {MIGRATE_HINT}"
                )
            raise
        self.written += len(self.pending)
        self.pending.clear()

    @property
    def skipped_total(self) -> int:
        return self.skipped_dup + self.skipped_empty


class DryRunWriter(TableWriter):
    """dry-run 用：什么都不写，只按同样的口径统计 inserted/updated/skipped。"""

    def flush(self) -> None:  # noqa: D102
        self.written += len(self.pending)
        self.pending.clear()


# ---------------------------------------------------------------------------
# 十、填充率 / 样例展示
# ---------------------------------------------------------------------------


class FillCounter:
    """统计每个目标字段的非空率。"""

    def __init__(self, columns):
        self.columns = columns
        self.filled = Counter()
        self.total = 0

    def add(self, record: dict) -> None:
        self.total += 1
        for column in self.columns:
            value = record.get(column)
            if value is None or value == "":
                continue
            if column == "product_count" and value == 0:
                continue  # 0 是「没抓到」，不算填充
            self.filled[column] += 1

    def report(self, title: str) -> None:
        print(f"  字段填充率（分母 {self.total:,} 行）：")
        if not self.total:
            print("    （无数据）")
            return
        for column in self.columns:
            n = self.filled.get(column, 0)
            rate = 100.0 * n / self.total
            bar = "#" * int(rate / 5)
            print("    %-14s %7d  %6.2f%%  %s" % (column, n, rate, bar))


def abbrev(value, limit: int = 120):
    """样例展示时截断超长字符串。"""
    if not isinstance(value, str):
        return value
    if len(value) <= limit:
        return value
    return value[:limit] + f"…(共 {len(value)} 字符)"


def print_samples(samples, label: str) -> None:
    print(f"  {label}前 {len(samples)} 条样例：")
    for i, record in enumerate(samples, 1):
        print(f"  --- 样例 {i} ---")
        print(json.dumps({k: abbrev(v) for k, v in record.items()}, ensure_ascii=False, indent=4))


# ---------------------------------------------------------------------------
# 十一、主流程
# ---------------------------------------------------------------------------


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="import_catalog.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "公开名录导入器 + 脱敏：把豆包爬取的 payload_*.json 清洗后幂等写入\n"
            "catalog_exhibitors / catalog_products 两张表。\n\n"
            "特性：\n"
            "  * 按 sheets[].columns 动态取列（不按位置硬编码，兼容列名多余空格）\n"
            "  * 手机号 / 座机 / 邮箱 / 微信 / QQ / 联系人 统一脱敏为 [联系方式已隐藏]\n"
            "  * INSERT ... ON CONFLICT DO UPDATE，可反复重跑（相同唯一键只更新）\n"
            "  * 不 import FastAPI app，直接 sqlite3 写库，不触发后端启动生命周期"
        ),
        epilog=(
            "示例：\n"
            "  python scripts/import_catalog.py --dry-run --limit 200\n"
            "  python scripts/import_catalog.py --db %TEMP%\\catalog_try.db --limit 200\n"
            "  python scripts/import_catalog.py --only products\n"
            "\n"
            "提示：目标表由 scripts/migrate_catalog_tables.py 创建，表缺失时本脚本会直接报错退出。"
        ),
    )
    parser.add_argument(
        "--source", default=DEFAULT_SOURCE, metavar="目录",
        help=f"爬取产物目录（默认：{DEFAULT_SOURCE}）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只解析 + 清洗 + 统计，不写库；会以只读方式打开数据库",
    )
    parser.add_argument(
        "--limit", type=int, default=0, metavar="N",
        help="每种（展商/展品）最多处理 N 条，用于快速验证；0 表示不限（默认 0）",
    )
    parser.add_argument(
        "--only", choices=("exhibitors", "products"), default=None,
        help="只导一边：exhibitors 或 products；不填为两边都导",
    )
    parser.add_argument(
        "--db", default=None, metavar="路径",
        help=("SQLite 数据库路径（默认 CWD 下的 expohub-backend/expohub.db，"
              "找不到则用脚本上一级的 expohub.db）"),
    )
    parser.add_argument(
        "--batch", type=int, default=1000, metavar="N",
        help="每 N 行提交一次事务（默认 1000）",
    )
    parser.add_argument(
        "--link-history", action="store_true",
        help="允许把「历史各届」类汇总名录按品牌词挂到某一届展会上（默认不挂，留 NULL）",
    )
    parser.add_argument(
        "--samples", type=int, default=3, metavar="N",
        help="打印前 N 条清洗后样例（默认 3）",
    )
    parser.add_argument(
        "--fill-rate", action="store_true",
        help="打印字段填充率（--dry-run 已自动开启）",
    )
    return parser.parse_args(argv)


def process_exhibitors(args, conn, matcher, san, writer_cls, existing_keys, files,
                       expo_stats) -> dict:
    """展商：读 → 清洗 → 去重 → 写。返回统计与样例。"""
    print(f"  展商源文件 {len(files)} 个")
    writer = writer_cls(conn, EXHIBITORS_TABLE, EXHIBITOR_TARGET_COLUMNS,
                        EXHIBITOR_CONFLICT, existing_keys, args.batch)
    fills = FillCounter(EXHIBITOR_TARGET_COLUMNS)
    samples = []
    rows_read = 0
    for _path, raw in iter_source_records(files, EXHIBITOR_SOURCE_ALIASES, "展商"):
        rows_read += 1
        record = clean_exhibitor_row(raw, matcher)
        # 先去重（重复行不再浪费时间脱敏），再脱敏，保证统计口径 = 真正入库行数
        key = writer.key_of(record)
        if key is None:
            writer.skipped_empty += 1
            continue
        if writer.is_duplicate(key):
            writer.skipped_dup += 1
            continue
        record = san.clean_record(record, EXHIBITOR_PII_FIELDS)
        outcome = writer.add(record)
        if outcome == "skipped":
            continue
        fills.add(record)
        # 展会关联统计只算「真正入库」的行（去重后的口径，能与库里的行数对上）
        if matcher is not None:
            _eid, _rule, _title = matcher.match(record["expo_name"], record["city"])
            entry = expo_stats.get(record["expo_name"])
            if entry is None:
                expo_stats[record["expo_name"]] = [1, _eid, _rule, _title]
            else:
                entry[0] += 1
        if len(samples) < max(0, args.samples):
            samples.append(record)
        if args.limit and fills.total >= args.limit:
            break
    writer.flush()
    return {
        "rows_read": rows_read,
        "writer": writer,
        "fills": fills,
        "samples": samples,
        "files": len(files),
    }


def process_products(args, conn, san, writer_cls, existing_keys, exhibitor_ids,
                     known_exhibitor_keys, files) -> dict:
    print(f"  展品源文件 {len(files)} 个")
    writer = writer_cls(conn, PRODUCTS_TABLE, PRODUCT_TARGET_COLUMNS,
                        PRODUCT_CONFLICT, existing_keys, args.batch)
    fills = FillCounter(PRODUCT_TARGET_COLUMNS)
    samples = []
    rows_read = 0
    link_hit = 0
    link_other = 0
    link_miss = 0
    for _path, raw in iter_source_records(files, PRODUCT_SOURCE_ALIASES, "展品"):
        rows_read += 1
        record, linkable = clean_product_row(raw, exhibitor_ids, known_exhibitor_keys)
        key = writer.key_of(record)
        if key is None:
            writer.skipped_empty += 1
            continue
        if writer.is_duplicate(key):
            writer.skipped_dup += 1
            continue
        record = finalize_product_record(record, san)
        outcome = writer.add(record)
        if outcome == "skipped":
            continue
        fills.add(record)
        if record.get("exhibitor_id") is not None:
            link_hit += 1
        elif linkable:
            link_other += 1
        else:
            link_miss += 1
        if len(samples) < max(0, args.samples):
            samples.append(record)
        if args.limit and fills.total >= args.limit:
            break
    writer.flush()
    return {
        "rows_read": rows_read,
        "writer": writer,
        "fills": fills,
        "samples": samples,
        "files": len(files),
        "link_hit": link_hit,
        "link_pending": link_other,
        "link_miss": link_miss,
    }


def print_file_discovery(founds: dict) -> None:
    print("[1] 源文件发现")
    for kind, groups in founds.items():
        label = "展商" if kind == "exhibitors" else "展品"
        for pattern, paths in groups:
            print(f"  {label} {pattern:<20} {len(paths):>3} 个")
            if not paths:
                print(f"    [warn] 目录里没有匹配 `{pattern}` 的文件", file=sys.stderr)


def print_expo_report(matcher: ExpoMatcher, expo_stats: dict) -> None:
    print("[4] 展会关联（exhibitions 表）")
    if matcher is None:
        print("  （跳过：数据库不可读或没有 exhibitions 表）")
        return
    if not matcher.entries:
        print("  （跳过：exhibitions 表为空）")
        return
    print(f"  exhibitions 候选 {len(matcher.entries)} 条")
    if not expo_stats:
        print("  （本次未处理展商，无源展会名可统计）")
        return
    print("  " + _pad("源展会名称", 40) + _pad_l("入库行数", 10) + "  关联结果")
    ordered = sorted(expo_stats.items(), key=lambda kv: -kv[1][0])
    shown = ordered[:EXPO_REPORT_LIMIT]
    for expo_name, entry in shown:
        cnt, eid, rule, title = entry
        target = f"#{eid} {title}" if eid else "NULL"
        print("  " + _pad(abbrev(expo_name, 38), 40) + _pad_l(f"{cnt:,}", 10)
              + "  " + _pad(abbrev(target, 46), 48) + f"[{rule}]")
    if len(ordered) > len(shown):
        print(f"  …（另有 {len(ordered) - len(shown)} 个源展会名未显示，"
              f"多为「历史各届/ID:xxx」分桶，全部留 NULL）")
    unmatched = [k for k, v in expo_stats.items() if v[1] is None]
    if unmatched:
        print(f"  未关联 {len(unmatched)} 个源展会名称（这些行 exhibition_id 写 NULL）：")
        for name in unmatched[:10]:
            print(f"    - {name}")


def main(argv=None) -> int:
    harden_stdout()
    args = parse_args(argv)
    started = time.perf_counter()

    if args.limit < 0:
        print("[ERROR] --limit 不能为负数", file=sys.stderr)
        return 2
    if args.batch < 1:
        print("[ERROR] --batch 必须 >= 1", file=sys.stderr)
        return 2

    source = os.path.abspath(os.path.expanduser(args.source))
    db_path = resolve_db_path(args.db)
    if not os.path.isdir(source):
        print(f"[ERROR] 数据源目录不存在：{source}", file=sys.stderr)
        return 2

    discovered = discover_files(source)
    files_by_kind = {
        kind: [p for _pattern, paths in groups for p in paths]
        for kind, groups in discovered.items()
    }
    only = args.only
    do_exhibitors = only in (None, "exhibitors")
    do_products = only in (None, "products")

    hr("=")
    print("公开名录导入器 · 运行摘要")
    hr("=")
    print(f"数据源目录 : {source}")
    print(f"数据库     : {db_path}  {'（已存在）' if os.path.isfile(db_path) else '（不存在）'}")
    print(f"运行模式   : {'DRY-RUN（只读，不写库）' if args.dry_run else '写库模式'}")
    print(f"参数       : only={only or 'all'}  limit={args.limit or '不限'}  batch={args.batch}"
          f"  link_history={'开' if args.link_history else '关'}")
    hr()
    print_file_discovery(discovered)

    # ---- 数据库准备 ----
    conn = None
    matcher = None
    existing_exhibitor_keys: set = set()
    existing_product_keys: set = set()
    expo_stats: dict = {}
    if not os.path.isfile(db_path):
        if not args.dry_run:
            print(f"[ERROR] 数据库不存在：{db_path}", file=sys.stderr)
            print(f"        请先执行：python {MIGRATE_HINT}", file=sys.stderr)
            return 2
        print(f"[warn] 数据库不存在（{db_path}），dry-run 将跳过展会关联与 inserted/updated 估算",
              file=sys.stderr)
    else:
        try:
            conn = open_db(db_path, readonly=args.dry_run)
        except sqlite3.DatabaseError as exc:
            print(f"[ERROR] 无法打开数据库 {db_path}：{exc}", file=sys.stderr)
            return 2
        if not args.dry_run:
            ok = True
            if do_exhibitors:
                ok = ensure_table(conn, EXHIBITORS_TABLE, EXHIBITOR_TARGET_COLUMNS, "展商") and ok
            if do_products:
                ok = ensure_table(conn, PRODUCTS_TABLE, PRODUCT_TARGET_COLUMNS, "展品") and ok
            if not ok:
                return 2
        else:
            for table in (EXHIBITORS_TABLE, PRODUCTS_TABLE):
                if not table_columns(conn, table):
                    print(f"[warn] dry-run：目标表 `{table}` 还不存在，"
                          f"inserted/updated 只做预估，展会关联仍可用", file=sys.stderr)
        if do_exhibitors or do_products:
            matcher = ExpoMatcher(load_exhibitions(conn), allow_history=args.link_history)
        if do_exhibitors:
            existing_exhibitor_keys = load_existing_keys(conn, EXHIBITORS_TABLE, EXHIBITOR_CONFLICT)
        if do_products:
            existing_product_keys = load_existing_keys(conn, PRODUCTS_TABLE, PRODUCT_CONFLICT)

    writer_cls = DryRunWriter if args.dry_run else TableWriter
    san_exhib = Sanitizer("展商")
    san_prod = Sanitizer("展品")
    pre_existing_exhibitors = len(existing_exhibitor_keys)
    pre_existing_products = len(existing_product_keys)

    # ---- 展商 ----
    exhib_result = None
    if do_exhibitors:
        hr()
        print("[2] 展商清洗" + ("（dry-run）" if args.dry_run else "并写库"))
        exhib_result = process_exhibitors(
            args, conn, matcher, san_exhib, writer_cls, existing_exhibitor_keys,
            files_by_kind["exhibitors"], expo_stats,
        )
        w = exhib_result["writer"]
        print(f"  读取 {exhib_result['rows_read']:,} 行 → 有效 {w.written:,} 行，"
              f"skipped {w.skipped_total:,}"
              f"（重复键 {w.skipped_dup:,} + 缺主键 {w.skipped_empty:,}）")
        if args.dry_run:
            print(f"  预估：inserted {w.inserted:,} / updated {w.updated:,}"
                  f"（跑之前库里已有 {pre_existing_exhibitors:,} 条）")
        else:
            print(f"  写库：inserted {w.inserted:,} / updated {w.updated:,} / "
                  f"skipped {w.skipped_total:,}")
        if args.dry_run or args.fill_rate:
            exhib_result["fills"].report("展商")

    # ---- 展品 ----
    prod_result = None
    if do_products:
        # 展商 id 映射：展商表 + 本轮插入结果
        exhibitor_ids: dict = {}
        known_exhibitor_keys: set = set()
        if conn is not None and table_columns(conn, EXHIBITORS_TABLE):
            try:
                for eid, expo, name in conn.execute(
                    f'SELECT id, expo_name, name FROM "{EXHIBITORS_TABLE}"'
                ):
                    key = (str(expo or ""), str(name or ""))
                    exhibitor_ids[key] = eid
                    known_exhibitor_keys.add(key)
            except sqlite3.DatabaseError as exc:
                print(f"[warn] 读取展商 id 失败（{exc}），exhibitor_id 将全为 NULL", file=sys.stderr)
        if args.dry_run and exhib_result is not None:
            # dry-run 展商没真正落库：把本轮解析出的键也算「可关联」，
            # 这样能提前看出关联率，而不是全报 NULL
            known_exhibitor_keys |= exhib_result["writer"].seen_keys

        hr()
        print("[3] 展品清洗" + ("（dry-run）" if args.dry_run else "并写库"))
        prod_result = process_products(
            args, conn, san_prod, writer_cls, existing_product_keys,
            exhibitor_ids, known_exhibitor_keys, files_by_kind["products"],
        )
        w = prod_result["writer"]
        print(f"  读取 {prod_result['rows_read']:,} 行 → 有效 {w.written:,} 行，"
              f"skipped {w.skipped_total:,}"
              f"（重复键 {w.skipped_dup:,} + 缺主键 {w.skipped_empty:,}）")
        if args.dry_run:
            print(f"  预估：inserted {w.inserted:,} / updated {w.updated:,}"
                  f"（跑之前库里已有 {pre_existing_products:,} 条）")
        else:
            print(f"  写库：inserted {w.inserted:,} / updated {w.updated:,} / "
                  f"skipped {w.skipped_total:,}")
        linked = prod_result["link_hit"]
        pending = prod_result["link_pending"]
        miss = prod_result["link_miss"]
        total = linked + pending + miss
        if args.dry_run:
            print(f"  展商回填（dry-run 预估）：{total:,} 行里 {total - miss:,} 行能在展商名录中"
                  f"找到对应展商（{100.0 * (total - miss) / total:.1f}%）" if total else
                  "  展商回填（dry-run 预估）：无数据")
            print(f"    其中库内已有展商可直接填 id {linked:,} 行；"
                  f"需靠本轮展商一起入库 {pending:,} 行；名录里没有 {miss:,} 行")
        else:
            print(f"  展商回填：exhibitor_id 已填 {linked:,} 行；"
                  f"名录里找不到对应展商 {miss:,} 行（写 NULL）")
        if args.dry_run or args.fill_rate:
            prod_result["fills"].report("展品")

    # ---- 展会关联报告 ----
    hr()
    print_expo_report(matcher, expo_stats)
    # ---- 脱敏统计 ----
    hr()
    print("[5] 脱敏统计")
    for san, kind in ((san_exhib, "展商"), (san_prod, "展品")):
        if (kind == "展商" and not do_exhibitors) or (kind == "展品" and not do_products):
            continue
        san.report()
    total_scanned = (san_exhib.rows_scanned if do_exhibitors else 0) + \
                    (san_prod.rows_scanned if do_products else 0)
    print(f"  合计扫描行数 {total_scanned:,}（展商 {san_exhib.rows_scanned if do_exhibitors else 0:,}"
          f" / 展品 {san_prod.rows_scanned if do_products else 0:,}）")
    print(f"  替换标记统一为 {PII_MASK}")

    # ---- 样例 ----
    if args.samples > 0:
        hr()
        print("[6] 清洗后样例")
        if exhib_result:
            print_samples(exhib_result["samples"], "展商 ")
        if prod_result:
            print_samples(prod_result["samples"], "展品 ")

    # ---- 收尾 ----
    hr("=")
    elapsed = time.perf_counter() - started
    print(f"完成，用时 {elapsed:.2f}s")
    if args.dry_run:
        print("DRY-RUN：未写入任何数据。")
    if conn is not None:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
