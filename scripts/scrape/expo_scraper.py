"""展会公开信息采集骨架（合规优先，默认不联网、不落库）

设计目标：把「绕过举办方也能拿到展会信息」这件事拆成**可审计的四步**：
    抓取（适配器） → 规范化（字段白名单） → 去重与人工复核 → 走平台导入接口落库

安全默认值：
    * 默认 --dry-run：只产出 JSON，不推送任何服务
    * 默认不联网：除非 sources.json 里显式 enabled=true 且传 --allow-network
    * 每个来源先读 robots.txt，被 Disallow 的来源直接跳过（不允许用 --force 绕过）
    * 字段白名单：只保留 标题/起止日期/地点/简介/封面/来源链接；**任何联系方式类字段一律丢弃并记录**
    * 请求间隔、单来源最大页数、超时都可配置，避免给对方站点造成压力

用法：
    # 1) 离线自测（不需要网络，验证管道与字段白名单）
    python scripts/scrape/expo_scraper.py --fixture docs/evidence/scrape_fixture.json --out out/demo.json

    # 2) 真实抓取（需 sources.json 里 enabled=true 且显式允许联网）
    python scripts/scrape/expo_scraper.py --allow-network --out out/exhibitions.json

    # 3) 人工复核后，推送到平台批量导入接口（管理员 token）
    python scripts/scrape/expo_scraper.py --push out/exhibitions.json \
        --api http://127.0.0.1:8002 --token <admin_access_token>

注意：本文件是**骨架**。真实站点需要按站点写 parser 适配器（当前实现 jsonld 与 demo_fixture 两种），
在写适配器之前请先读 docs/2026-10-19-数据抓取方案与合规边界.md。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone

USER_AGENT = "X-Expo-PublicInfoBot/0.1 (+contact: platform-ops@example.com)"
FIELD_WHITELIST = ("title", "start_date", "end_date", "location", "description", "cover_image")
PROVENANCE_FIELDS = ("source_id", "source_name", "source_url", "fetched_at")
# 个人信息/联系方式类字段：命中即丢弃（不是脱敏，是根本不采集）
FORBIDDEN_KEY_PATTERNS = re.compile(
    r"(phone|mobile|tel|email|mail|contact|wechat|qq|wa_?number|"
    r"联系|电话|手机|邮箱|微信|姓名|person|organizer_phone)", re.I)


# ----------------------------------------------------------------------------
# 抓取层
# ----------------------------------------------------------------------------

class RobotsCache:
    """按来源缓存 robots.txt 判定结果"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(origin + "/robots.txt")
            try:
                req = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    rp.parse(resp.read().decode("utf-8", "ignore").splitlines())
            except Exception:
                # 取不到 robots.txt 时保守处理：默认不允许自动抓取
                rp = None
            self._cache[origin] = rp
        rp = self._cache[origin]
        if rp is None:
            return False
        return rp.can_fetch(USER_AGENT, url)


def http_get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, "ignore")


def extract_jsonld_events(html: str) -> list[dict]:
    """通用适配器：从 schema.org Event JSON-LD 中抽取展会条目（大多数展会站都带）"""
    events: list[dict] = []
    for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
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
                location = ""
                if isinstance(loc, dict):
                    location = loc.get("name") or loc.get("address") or ""
                elif isinstance(loc, str):
                    location = loc
                events.append({
                    "title": (node.get("name") or "").strip(),
                    "start_date": (node.get("startDate") or "").strip(),
                    "end_date": (node.get("endDate") or node.get("startDate") or "").strip(),
                    "location": str(location).strip(),
                    "description": (node.get("description") or "").strip()[:500],
                    "cover_image": (node.get("image") if isinstance(node.get("image"), str) else "") or None,
                })
            for value in node.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
    return events


# ----------------------------------------------------------------------------
# 规范化 / 清洗
# ----------------------------------------------------------------------------

def sanitize(row: dict, source: dict, url: str) -> dict | None:
    """字段白名单 + 丢弃联系方式 + 基础校验。返回 None 表示该条不可用。"""
    dropped = [k for k in row if FORBIDDEN_KEY_PATTERNS.search(k)]
    clean = {k: v for k, v in row.items() if k in FIELD_WHITELIST and not FORBIDDEN_KEY_PATTERNS.search(k)}
    if dropped:
        print(f"    [guard] 丢弃联系方式类字段: {dropped}")

    clean["title"] = (clean.get("title") or "").strip()
    clean["location"] = (clean.get("location") or "").strip()
    if len(clean["title"]) < 4 or not clean["location"]:
        return None

    # 日期必须可解析（杜绝 0123-12-03 这类脏数据进库）
    for key in ("start_date", "end_date"):
        value = (clean.get(key) or "").strip()
        if not value:
            return None
        normalized = value[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", value) else value
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                dt = datetime.strptime(normalized, "%Y/%m/%d")
            except ValueError:
                return None
        if not (2000 <= dt.year <= 2100):
            return None
        clean[key] = normalized

    clean["description"] = (clean.get("description") or "").strip()[:500] or None
    clean.setdefault("cover_image", None)
    clean.update({
        "source_id": source.get("id"),
        "source_name": source.get("name"),
        "source_url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return clean


def dedupe(rows: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out = []
    for row in rows:
        key = (row["title"].strip().lower(), row["start_date"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


# ----------------------------------------------------------------------------
# 采集主流程
# ----------------------------------------------------------------------------

def collect(source: dict, robots: RobotsCache, allow_network: bool) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    rows: list[dict] = []
    list_url = source.get("list_url")
    if not list_url:
        return rows, ["缺少 list_url"]

    if not allow_network or not source.get("enabled"):
        print(f"  [skip] 来源 {source.get('id')} 未启用或未允许联网（enabled={source.get('enabled')}, allow_network={allow_network}）")
        return rows, []

    if not robots.allowed(list_url):
        return rows, [f"robots.txt 不允许抓取：{list_url}（已跳过，不提供绕过选项）"]

    delay = float(source.get("delay_seconds", 2))
    parser = source.get("parser", "jsonld")
    url = list_url
    pages = 0
    max_pages = int(source.get("max_pages", 1))
    while url and pages < max_pages:
        pages += 1
        try:
            html = http_get(url)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            errors.append(f"请求失败 {url}: {exc}")
            break
        if parser == "jsonld":
            items = extract_jsonld_events(html)
        else:
            errors.append(f"未知 parser：{parser}")
            break
        for item in items:
            row = sanitize(item, source, url)
            if row:
                rows.append(row)
        print(f"    {url} -> {len(items)} 条（累计 {len(rows)}）")
        url = None  # 骨架不自动翻页；具体站点翻页规则在适配器里实现
        time.sleep(delay)
    return rows, errors


def load_fixture(path: str, source: dict) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    items = data.get("items", data if isinstance(data, list) else [])
    rows = []
    for item in items:
        row = sanitize(item, source, source.get("list_url", f"fixture://{os.path.basename(path)}"))
        if row:
            rows.append(row)
    return rows


def push(api: str, token: str, rows: list[dict], status: str) -> int:
    """推送到平台批量导入接口（只送导入接口认识的字段）"""
    payload_rows = [
        {
            "title": r["title"],
            "start_date": r["start_date"],
            "end_date": r["end_date"],
            "location": r["location"],
            "status": status,
            "description": r.get("description"),
            "cover_image": r.get("cover_image"),
        }
        for r in rows
    ]
    body = json.dumps({"rows": payload_rows}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/platform/import/exhibitions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"[XX] 导入失败 HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')[:300]}")
        return 1
    data = result.get("data", {})
    print(f"[OK] 导入完成：成功 {data.get('success_count')}/{data.get('total')}")
    for item in data.get("results", []):
        if not item.get("ok"):
            print(f"  - 第{item.get('row')}行 {item.get('title')}: {item.get('reason')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="X-Expo 展会公开信息采集（合规骨架）")
    ap.add_argument("--sources", default=os.path.join(os.path.dirname(__file__), "sources.json"))
    ap.add_argument("--out", default="out/exhibitions.json")
    ap.add_argument("--fixture", help="离线夹具 JSON（不联网，用于自测管道）")
    ap.add_argument("--allow-network", action="store_true", help="允许真实联网抓取（默认禁止）")
    ap.add_argument("--push", nargs="?", const="", metavar="FILE", help="推送 JSON 到平台导入接口")
    ap.add_argument("--api", default="http://127.0.0.1:8002")
    ap.add_argument("--token", help="管理员 access_token（配合 --push）")
    ap.add_argument("--status", default="draft", help="导入后的展会状态（默认 draft，需人工复核再发布）")
    args = ap.parse_args()

    if args.push is not None:
        path = args.push or args.out
        if not args.token:
            print("[XX] --push 需要 --token（管理员登录后的 access_token）")
            return 2
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh).get("rows", [])
        return push(args.api, args.token, rows, args.status)

    source = {"id": "fixture", "name": "离线夹具", "enabled": True}
    robots = RobotsCache()
    all_rows: list[dict] = []
    errors: list[str] = []

    if args.fixture:
        rows = load_fixture(args.fixture, source)
        print(f"[fixture] 通过字段白名单 {len(rows)} 条")
        all_rows.extend(rows)
    else:
        if not os.path.exists(args.sources):
            print(f"[XX] 找不到来源配置：{args.sources}")
            return 2
        with open(args.sources, encoding="utf-8") as fh:
            sources = json.load(fh).get("sources", [])
        for src in sources:
            print(f"[source] {src.get('id')} {src.get('name')}")
            rows, errs = collect(src, robots, args.allow_network)
            all_rows.extend(rows)
            errors.extend(errs)

    rows = dedupe(all_rows)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "只含公开展会信息（标题/时间/地点/简介/封面/来源），不含任何联系方式；导入前请人工复核",
        "count": len(rows),
        "errors": errors,
        "rows": rows,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[OK] 输出 {len(rows)} 条 -> {args.out}")
    for err in errors:
        print("  [warn]", err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
