"""
去展网（qufair.com）展会规模索引采集——E1 缺口的第三条数据源。

为什么需要这一层：
    官网首页能抽到的规模数已经抽干了（可算比值的 35/94）。剩下的展，页面本身
    就只写一边或一边都不写。去展网这类聚合平台把「展览面积 / 展商数量 / 观众数量」
    三个数**结构化写在详情页固定位置**，正好补上缺口。

但它是**二手数据，且已实测有系统性偏差**：
    CMEF       去展网 观众 150,000  vs 官网 200,000+   → 低 25%
    CHINAPLAS  去展网 观众 250,000  vs 官网 310,000+   → 低 19%
               去展网 展商   3,900  vs 官网   4,700+   → 低 17%
    展商数基本准，观众数系统性偏低 20~25%，且有时给的是"下一届预估"而不是已办一届。

所以本脚本**只建索引，不做任何判定**。匹配与填充规则全部在 match_qufair.py 里，
且遵守一条硬规则：**成对使用、绝不混源**。理由见该脚本头部。

做法：
    · 从 robots 里声明的 sitemap_expo.xml 取全部详情页 URL（当前 2670 个）。
      站点自己把 sitemap 写进 robots，就是允许被索引的意思，比漫无目的翻列表页规矩。
    · 每页只截 <title> 与三个字段，**不做全文清洗**——2670 页全文既慢又没必要。
    · 断点续爬：index 已存在就跳过已抓的 id，中断重跑不重来。
    · 礼貌：并发 4、每请求之间加随机抖动，不做突刺。

落盘：
    data/batch4/qufair_index.json   {id: {title, area, exhibitors, visitors, year, error}}

用法：
    python scripts/persona/collect_qufair.py --limit 20      # 先试 20 页
    python scripts/persona/collect_qufair.py                 # 全量（约 2670 页）
    python scripts/persona/collect_qufair.py --refresh       # 忽略已有索引重抓
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data"
OUT_DIR = DATA / "batch4"
INDEX = OUT_DIR / "qufair_index.json"
SITEMAP = "https://www.qufair.com/sitemap_expo.xml"
BASE = "https://www.qufair.com/"

sys.path.insert(0, str(HERE))
from collect_skeleton import _ROBOTS, fetch  # noqa: E402

MAX_WORKERS = 4

# 详情页三个字段写死在固定位置：`展览面积：23000平方米 展商数量：500家 观众数量：18000人`
# 用 [^<\n]{1,24} 截到下一个标签为止，避免把后面的"行业专业展 / 4.9 规模度"也吃进来。
_FLD = {
    "area": re.compile(r"展览面积[：:]\s*([^<\n]{1,24})"),
    "exhibitors": re.compile(r"展商数量[：:]\s*([^<\n]{1,24})"),
    "visitors": re.compile(r"观众数量[：:]\s*([^<\n]{1,24})"),
}
_TITLE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
# 标题末尾的 "-去展网" 与前置的年份都要拆出来：
# "中国（上海）国际果蔬展览会_2026年地点及门票-去展网"
_YEAR = re.compile(r"(20\d{2})\s*年")
_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)")

# 城市与展期不是"规模字段"，但它们是**匹配用的证据**：
# 只按名字匹配会撞车（"上海国际鞋展" vs "广州国际鞋展"、"中国国际五金展" 每年两届）。
#
# 页面结构是标签和值被 HTML 拆开的，直接抓文本抓不到：
#   <span>展会地点：</span><address>…<a title="中国展会">中国</a>-<a title="上海展会">上海</a>- 崧泽大道333号…
#   <span>展会时间：</span><time datetime="2027-04-07/2027-04-10">2027年04月07日 - 04月10日</time>
# 所以城市从 `<a title="XX展会">` 取（跳过"中国"这一层国家），
# 展期直接用 `<time datetime>` 的机器可读值，比解析中文日期可靠。
_LOC_BLOCK = re.compile(r"展会地点[：:]\s*</span>(.{0,600}?)(?:</li>|<li)", re.S)
_LOC_CITY = re.compile(r'title="([^"]{2,12})展会"')
_TIME_ATTR = re.compile(r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})"')
_TIME_TEXT = re.compile(r"展会时间[：:]\s*(?:<[^>]+>)*\s*([^<\n]{4,40})")
_DATE = re.compile(r"(20\d{2})\s*[年.\-/]\s*(\d{1,2})\s*[月.\-/]\s*(\d{1,2})")
_NOT_CITY = {"中国", "国际", "国内", "海外", "全球"}


def _num(s: str | None) -> int | None:
    if not s:
        return None
    m = _NUM.search(s.replace(" ", ""))
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    if "万" in s:
        v *= 10_000
    return int(round(v)) if v > 0 else None


def clean_title(t: str) -> str:
    t = re.sub(r"\s*[-—|]\s*去展网\s*$", "", t.strip())
    t = re.sub(r"_\s*20\d{2}\s*年.*$", "", t)
    return t.strip()


def parse(url: str, html: str) -> dict:
    m = _TITLE.search(html)
    title = clean_title(m.group(1)) if m else ""
    rec = {"url": url, "title": title, "error": None}
    y = _YEAR.search(m.group(1)) if m else None
    rec["year"] = int(y.group(1)) if y else None
    hit = 0
    for k, rx in _FLD.items():
        mm = rx.search(html)
        rec[k] = _num(mm.group(1)) if mm else None
        hit += 1 if rec[k] else 0

    # 匹配证据（不是规模数据，缺了不影响可用性）
    lb = _LOC_BLOCK.search(html)
    cities = [c for c in _LOC_CITY.findall(lb.group(1)) if c not in _NOT_CITY] if lb else []
    rec["city"] = cities[0] if cities else ""

    ta = _TIME_ATTR.search(html)
    if ta:
        rec["start_date"], rec["end_date"] = ta.group(1), ta.group(2)
    else:
        tt = _TIME_TEXT.search(html)
        dm = _DATE.search(tt.group(1)) if tt else None
        rec["start_date"] = ("%s-%02d-%02d" % (dm.group(1), int(dm.group(2)), int(dm.group(3)))
                             if dm else None)
        rec["end_date"] = None

    if not title:
        rec["error"] = "no_title"
    elif hit == 0:
        rec["error"] = "no_scale_fields"
    return rec


def one(url: str) -> dict:
    sid = url.rstrip("/").rsplit("/", 1)[-1]
    try:
        st, _, html = fetch(url, timeout=20)
    except Exception as ex:                              # noqa: BLE001
        return {"url": url, "title": "", "error": f"{type(ex).__name__}"}
    if st >= 400:
        return {"url": url, "title": "", "error": f"http_{st}"}
    return parse(url, html)


def load_sitemap() -> list[str]:
    st, _, body = fetch(SITEMAP, timeout=40)
    if st >= 400:
        raise RuntimeError(f"sitemap http_{st}")
    locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", body)
    # 只留展会详情页（纯数字路径）。sitemap 里混了行业页/资讯页。
    return [u for u in locs if re.search(r"/\d{3,}$", u)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=MAX_WORKERS)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--enrich", action="store_true",
                    help="只重抓缺少 city/start_date 的旧记录（补匹配证据，不动规模数）")
    ap.add_argument("--only", default="", help="指定若干 id，便于定向补抓")
    args = ap.parse_args()

    why = _ROBOTS.reason(BASE)
    if why not in ("allow", "absent"):
        print("✗ robots 不允许：%s" % why, file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prev: dict[str, dict] = {}
    if INDEX.exists() and not args.refresh:
        try:
            prev = json.loads(INDEX.read_text(encoding="utf-8"))
        except ValueError:
            prev = {}

    urls: list[str] = []
    if not (args.enrich or args.only):
        urls = load_sitemap()
        print("去展网详情页 %d 个；索引已有 %d 条" % (len(urls), len(prev)))

    # 已抓成功的跳过；失败的也跳过（避免每次重跑都去撞同一个坏页），
    # 要重试就加 --refresh。
    if args.enrich:
        # 索引是一批批长大的：先跑的那批没有 city/start_date 字段（当时还没写解析），
        # 补一遍才有匹配证据。城市抓不到就说明解析没命中，也值得重抓一次。
        todo = [v["url"] for v in prev.values()
                if not v.get("city") or not v.get("start_date")]
    elif args.only:
        todo = [BASE + i.strip() for i in args.only.split(",") if i.strip()]
    else:
        todo = [u for u in urls if u.rsplit("/", 1)[-1] not in prev]
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("没有需要抓的页面。")
    else:
        print("本轮抓 %d 页（并发 %d）" % (len(todo), args.workers))

    done = dict(prev)
    t0 = time.time()
    lock_free = True
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {}
        for u in todo:
            futs[pool.submit(one, u)] = u
            # 提交端限速，比每线程 sleep 更稳（线程池里 sleep 会互相错开但总量不可控）
            time.sleep(random.uniform(0.05, 0.15))
        for n, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            sid = r["url"].rstrip("/").rsplit("/", 1)[-1]
            done[sid] = r
            if n % 100 == 0 or n == len(todo):
                INDEX.write_text(json.dumps(done, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
                print("  [%4d/%4d] 已保存 %d 条  %.0f 秒" % (
                    n, len(todo), len(done), time.time() - t0))

    INDEX.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = [v for v in done.values() if not v.get("error")]
    full = [v for v in ok if v.get("visitors") and v.get("exhibitors")]
    print("\n" + "=" * 70)
    print("索引 %d 条 ｜ 可用 %d ｜ 三个数齐全 %d ｜ 用时 %.0f 秒" % (
        len(done), len(ok), len(full), time.time() - t0))
    errs: dict[str, int] = {}
    for v in done.values():
        if v.get("error"):
            errs[v["error"]] = errs.get(v["error"], 0) + 1
    if errs:
        print("失败分布：" + " ｜ ".join(f"{k}×{n}" for k, n in
                                    sorted(errs.items(), key=lambda x: -x[1])[:6]))
    print("→ %s" % INDEX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
