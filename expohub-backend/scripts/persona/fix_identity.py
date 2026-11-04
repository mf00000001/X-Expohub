"""
身份层修复：展名规范化 + 城市校正

## 为什么这个脚本比补规模数更紧急

规模数缺了，页面显示"未公开"，还能看。展名错了，页面显示
"Maintenance - International Lo…"、"上海颖展展览服务有限公司"、
"虎门会展网"——**这不是数据少，这是数据错**，而错的数据比没有数据更糟：
用户会以为"上海颖展展览服务有限公司"是个展会，或者干脆认为这站是垃圾。

批次 0~3 的采集把页面的 `<title>` 直接当了展名。页面标题有三种典型污染：
1. 站点名/公司名（"虎门会展网"、"上海颖展展览服务有限公司"）
2. 多个页面 meta 拼在一起（"深圳礼品展、深圳消费电子展、深圳包装展…|礼品展|"）
3. 抓到了 404/维护页（"Maintenance - International…"）

而 `data/expo_candidates_final.json` 里**本来就有** 100 个经 WebSearch 查证过的
规范全称（`official_name` 字段，note 里写明 "v2: 经 WebSearch 查证后合并，
verify 字段记录证据强度"）。这批数据一直没被用起来，等于白爬。

## 三类改动，风险等级不同，处理方式也不同

| 改动 | 依据 | 风险 | 做法 |
|---|---|---|---|
| 写 `name_official` | candidates 查证结论 | 低 | 无条件写入 |
| 覆盖 `name_cn` | 仅当原名命中"污染特征" | 中 | 先存 `name_raw` 再覆盖 |
| 改 `city` | 名称里出现的地名 | 中 | 只在冲突时改，记 note |

**名字不脏就不改。** 库内名多数是官网 H1（"第三十五届上海国际酒店及餐饮业博览会"），
带届次、有真实感，比规范全称更适合展示。只有确认为污染才替换。

## city 为什么以"名称里的地名"为准

candidates 的 `city` 字段本身就靠不住：b-crossborder 的名字是
"CCBEC 中国（深圳）跨境电商展览会"，而 `city` 写的是"杭州"；
b-furniture-wood 名字含"上海"、`city` 写"广州"。库内的 city 反而多数是对的。

名称是查证过的（含地名是展会命名的硬事实），城市字段是表单填的。
所以冲突时信名称。这条规则救回了 china-logistics：
库内 city=广州，但官方名是"中国（**深圳**）国际物流与供应链博览会"。

## 不做什么

- 不改 `venue_name`（没有可靠第二来源）
- 不删重复展（先报告，人工决定留哪个）
- 不动任何规模数（那是 estimate_fill.py 的活）

用法：
    python scripts/persona/fix_identity.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select  # noqa: E402

from app.modules.persona.db import PersonaSessionLocal  # noqa: E402
from app.modules.persona.models import Expo  # noqa: E402

CANDIDATES_PATH = Path(__file__).resolve().parents[2] / "data" / "expo_candidates_final.json"

# 地名 → 城市。**镇级地名必须映射到市**：古镇是中山的镇（灯都），
# 虎门是东莞的镇。否则按城市筛选"中山"时，灯博会会被漏掉。
CITY_BY_PLACE: dict[str, str] = {
    "北京": "北京", "上海": "上海", "广州": "广州", "深圳": "深圳",
    "杭州": "杭州", "南京": "南京", "成都": "成都", "重庆": "重庆",
    "武汉": "武汉", "西安": "西安", "青岛": "青岛", "宁波": "宁波",
    "厦门": "厦门", "苏州": "苏州", "无锡": "无锡", "东莞": "东莞",
    "虎门": "东莞", "佛山": "佛山", "中山": "中山", "古镇": "中山",
    "义乌": "义乌", "永康": "永康", "温州": "温州", "晋江": "晋江",
    "南宁": "南宁", "海口": "海口", "郑州": "郑州", "天津": "天津",
    "合肥": "合肥", "济南": "济南", "昆明": "昆明", "福州": "福州",
    "长沙": "长沙", "沈阳": "沈阳", "大连": "大连", "哈尔滨": "哈尔滨",
    "长春": "长春", "石家庄": "石家庄", "太原": "太原", "南昌": "南昌",
    "贵阳": "贵阳", "兰州": "兰州", "乌鲁木齐": "乌鲁木齐",
    "香港": "香港", "澳门": "澳门", "台北": "台北",
}

# 巡回展的城市标注。糖酒会春秋两届不同城市，API/药交会也是巡回，
# 这不是缺数据，是事实。"轮换"这个值要保留，不能当异常清掉。
ROTATING_CITIES = {"轮换", "巡回", "全国"}

# 名称污染特征。命中任意一条即判定为"抓错了标题"。
# 刻意写得窄：宁可漏改（用户在页面上看到长一点的官网标题），
# 也不要错改（把的真实展会名换成另一个展的）。
DIRTY_PATTERNS: list[tuple[str, str]] = [
    ("slug", "名称就是 slug，抽取失败"),
    ("pipe", "含竖线，多个页面 meta 拼在一起"),
    ("nav", "以「首页」开头，抓到导航或首页标题"),
    ("maintenance", "抓到 404 / 维护页"),
    ("company", "抓到公司名或站点名"),
    ("short", "名称过短"),
]


# 英文城市名 → 中文。cite 和 sial-china 的 city 字段是 "Shanghai"，
# 不映射的话按"上海"筛选时这两个展会消失——用户不会知道是拼写问题。
CITY_ALIAS: dict[str, str] = {
    "Shanghai": "上海", "Beijing": "北京", "Guangzhou": "广州",
    "Shenzhen": "深圳", "Hong Kong": "香港", "Jinjiang": "晋江",
    "Ningbo": "宁波", "Xiamen": "厦门", "Qingdao": "青岛",
    "Yiwu": "义乌", "Dongguan": "东莞", "Foshan": "佛山",
    "Hangzhou": "杭州", "Nanjing": "南京", "Chengdu": "成都",
    "Chongqing": "重庆", "Tianjin": "天津", "Wenzhou": "温州",
}


# 已知重复展：{重复条 slug: (保留条 slug, 说明)}
#
# 为什么手工列而不是自动判：两两比对在 94 个展上跑出 196 对"重复"，
# 因为"广州国际汽车展览会"和"广州国际照明展览会"剥掉公共词后
# 字符重叠率还很高。阈值调到能杀误报就又漏真重复，不值得。
# 4 对真候选里还有 1 对是误判（china-hardware 中国国际五金博览会 3 月
# 国展中心 vs cihs 中国国际五金展 10 月新国际——两个主办方两个展），
# 所以最终只认这 3 对。
#
# 处理方式是标 excluded 而不是删除：观测记录挂在 expo_id 上，
# 删了主档观测就成了孤儿（FK CASCADE 会连观测一起删）。
# 打标记能保住溯源，列表里也不会重复出现。
KNOWN_DUPLICATES: dict[str, tuple[str, str]] = {
    "sial-china": (
        "b-catering",
        "与 b-catering 同一展会（2027-05-18 SIAL 西雅上海），对方已有完整规模数据",
    ),
    "ccbef": (
        "b-crossborder",
        "与 b-crossborder 同一展会（2027-08-18 深圳跨境电商展 CCBEC），对方有观众数",
    ),
    "reed-gift-sz": (
        "b-premium-gift",
        "与 b-premium-gift 同一展会（深圳礼品及家居用品展），两条均无规模数据",
    ),
}


def _normalize_city(city: str | None) -> str | None:
    """去掉「市」后缀 + 英文名映射，让同一个城市只有一个筛选值。"""
    if not city:
        return None
    c = city.strip()
    if c in ROTATING_CITIES:
        return c
    if c in CITY_ALIAS:
        return CITY_ALIAS[c]
    if c.endswith("市") and len(c) > 2:
        c = c[:-1]
    return c


def _city_from_name(text: str) -> str | None:
    """
    从名称里嗅地名。按长度降序匹配，避免短地名抢先命中。

    "古镇" 和 "东莞" 都是 2 字，但古镇灯博会名字里只有"古镇"，
    所以两个都要能命中——这里用"最长的那个匹配"，同长时取先出现的。
    """
    if not text:
        return None
    hits = [(place, city) for place, city in CITY_BY_PLACE.items() if place in text]
    if not hits:
        return None
    hits.sort(key=lambda x: -len(x[0]))
    return hits[0][1]


def _core(name: str) -> str:
    """
    去掉噪声后取名称主干，用于判断"两个名字是不是同一个展"。

    必须剥掉的东西（每一条都来自实际误报）：
    - 届次："第 120 届"、"2026" —— 同一个展每届名字都带不同的届次
    - 括号内容："（百货会 CDATF）"、"（Auto China）" —— 缩写有无都可能
    - 空格和标点
    - 品类尾词："展览会 / 博览会 / 交易会 / 展" —— "中国国际教育展" 和
      "中国国际教育展览会" 是同一个展，尾词不同不该判成冲突

    早先没剥届次，结果 25 条"冲突"里 20 条是
    "第 120 届中国日用百货商品交易会" vs "中国日用百货商品交易会（百货会 CDATF）"
    这种同一个展的正常差异，把真正需要人看的 5 条淹掉了。
    """
    s = name or ""
    s = re.sub(r"[（(][^）)]*[）)]", "", s)          # 括号及内容
    s = re.sub(r"第\s*[\d一二三四五六七八九十百零]+\s*[届期]", "", s)
    s = re.sub(r"(19|20)\d{2}\s*年?", "", s)
    s = re.sub(r"[·・\-—_\s/、，,。.]", "", s)
    for suffix in ("展览会", "博览会", "交易会", "展销会", "展会", "展"):
        if s.endswith(suffix) and len(s) > len(suffix) + 3:
            s = s[: -len(suffix)]
            break
    return s


def _same_expo(a: str, b: str) -> bool:
    """
    字符级重叠率判定。不用编辑距离，因为中文展名里"国际/中国"这种
    公共前缀会虚高相似度。

    判据：较短主干里的字，有 60% 以上出现在较长主干中。

    **一边是英文名时直接判"同一展"**：字符重叠对中英对应完全无效
    （"electronica Shanghai" 和 "慕尼黑上海电子展" 一个字都不重叠，
    但就是同一个展）。这类只能靠人看，不该进冲突列表——
    早先没做这个豁免，12 条"冲突"里 6 条是中英对照的误报。
    """
    ca, cb = _core(a), _core(b)
    if not ca or not cb:
        return True  # 取不到主干就不判冲突，避免误报

    def _mostly_ascii(s: str) -> bool:
        if not s:
            return False
        ascii_n = sum(1 for ch in s if ord(ch) < 128)
        return ascii_n / len(s) > 0.6

    if _mostly_ascii(ca) or _mostly_ascii(cb):
        return True

    if ca in cb or cb in ca:
        return True
    short, long = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
    hit = sum(1 for ch in set(short) if ch in long)
    return hit / len(set(short)) >= 0.6


def detect_dirty(name: str | None, slug: str) -> str | None:
    """返回污染原因；干净返回 None。"""
    n = (name or "").strip()
    if not n:
        return DIRTY_PATTERNS[0][1]
    if n == slug:
        return DIRTY_PATTERNS[0][1]
    if "|" in n or "｜" in n:
        return DIRTY_PATTERNS[1][1]
    if n.startswith("首页"):
        return DIRTY_PATTERNS[2][1]
    if n.lower().startswith("maintenance"):
        return DIRTY_PATTERNS[3][1]
    if any(k in n for k in ("有限公司", "会展网", "展览服务", "展会网")):
        return DIRTY_PATTERNS[4][1]
    # 纯 ASCII 且短：多半是 slug 或英文截断
    if len(n) < 6 and re.fullmatch(r"[A-Za-z0-9 \-]+", n):
        return DIRTY_PATTERNS[5][1]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写库")
    args = ap.parse_args()

    if not CANDIDATES_PATH.exists():
        print(f"找不到候选名单: {CANDIDATES_PATH}")
        return 1

    data = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in data["expos"]}

    renamed: list[tuple[str, str, str, str]] = []
    city_fixed: list[tuple[str, str, str, str]] = []
    merged: list[tuple[str, str, str]] = []
    official_filled = 0
    conflicts: list[str] = []

    with PersonaSessionLocal() as db:
        expos = db.execute(select(Expo).order_by(Expo.id)).scalars().all()

        for expo in expos:
            cand = by_id.get(expo.slug) or {}
            # official_name 有 4 个条目为空（chic / chinaplas / cile / china-outdoor），
            # 但同一份候选名单的 name 字段有值。退一步用 name，总比留个 slug 强。
            official = (cand.get("official_name") or "").strip() or (cand.get("name") or "").strip() or None

            if official and expo.name_official != official:
                expo.name_official = official
                official_filled += 1

            # ---- 名字 ----
            dirty = detect_dirty(expo.name_cn, expo.slug)
            if dirty:
                if official:
                    if expo.name_raw is None:
                        expo.name_raw = expo.name_cn
                    renamed.append((expo.slug, expo.name_cn, official, dirty))
                    expo.name_cn = official
                else:
                    conflicts.append(f"{expo.slug}: 名称污染（{dirty}）但候选名单没有官方名，未改")
            elif official:
                # 名字不脏但和官方名差异很大 —— 可能是候选名单本身错了
                # （cite：库内是"China International Tire Expo"轮胎展，
                # 官方名写的是"中国国际电子信息博览会"，两个完全不同的展）。
                if not _same_expo(expo.name_cn, official):
                    conflicts.append(
                        f"{expo.slug}: 库内名「{expo.name_cn}」与官方名「{official}」无重叠，待人工核"
                    )

            # ---- 城市 ----
            # 三级证据，优先级从高到低：
            #   1. 名称里出现的地名（展会命名是硬事实，且名称已查证）
            #   2. 库内已有的 city（规范化后缀/英文名后）
            #   3. 候选名单的 city（实测这个字段会错，只能兜底）
            source_text = " ".join(filter(None, [expo.name_cn, official]))
            by_place = _city_from_name(source_text)
            current = _normalize_city(expo.city)
            cand_city = _normalize_city(cand.get("city"))

            if by_place and current != by_place:
                city_fixed.append((expo.slug, expo.city or "空", by_place,
                                   f"名称含「{[p for p in CITY_BY_PLACE if p in source_text][0]}」"))
                expo.city = by_place
            elif current:
                if current != expo.city:
                    city_fixed.append((expo.slug, expo.city or "空", current, "规范化"))
                    expo.city = current
            elif cand_city:
                # 名称里没地名、库内也没有 —— 用候选名单兜底。
                # 轮换展（糖酒会/API/药交会）的 "轮换" 也是有效值，不是缺失。
                city_fixed.append((expo.slug, "空", cand_city, "候选名单兜底"))
                expo.city = cand_city

        # ---- 去重 ----
        # 放在最后，此时名字和城市都已规范化，目标 slug 一定存在
        by_slug = {e.slug: e for e in expos}
        for dup_slug, (keep_slug, why) in KNOWN_DUPLICATES.items():
            dup, keep = by_slug.get(dup_slug), by_slug.get(keep_slug)
            if dup is None or keep is None:
                continue
            if dup.data_status == "excluded":
                continue
            dup.data_status = "excluded"
            dup.note = f"重复条目，已合并到 {keep_slug}：{why}"
            merged.append((dup_slug, keep_slug, why))

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    mode = "[dry] " if args.dry_run else ""
    print(f"{mode}候选名单匹配 {len(expos)} 个展，其中 {official_filled} 个补写规范全称")
    print()
    print(f"{mode}=== 修正名称 {len(renamed)} 条 ===")
    for slug, old, new, why in renamed:
        print(f"  {slug[:20]:22s} 「{old[:34]}」")
        print(f"  {'':22s} → 「{new}」   [{why}]")
    print()
    print(f"{mode}=== 修正城市 {len(city_fixed)} 条 ===")
    for slug, old, new, why in city_fixed:
        print(f"  {slug[:20]:22s} {old:8s} → {new:8s}  {why}")
    if merged:
        print()
        print(f"{mode}=== 标记重复 {len(merged)} 条（不删除，保留观测溯源）===")
        for dup, keep, why in merged:
            print(f"  {dup:20s} → 合并到 {keep:20s} {why}")
    print()
    if conflicts:
        print(f"=== 待人工核 {len(conflicts)} 条（未改动）===")
        for c in conflicts:
            print("  " + c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
