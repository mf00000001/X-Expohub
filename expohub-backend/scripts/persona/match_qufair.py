"""
把去展网索引匹配到我们的 94 个展，并**成对**补进画像库。

## 为什么必须"成对"，不能各补各的

去展网是二手数据，而且已实测有系统性偏差：

    CMEF       去展网观众 150,000(旧页) / 200,000(详情页)  vs 官网 200,000+
    CHINAPLAS  去展网观众 250,000  vs 官网 310,000+        → 低 19%
               去展网展商   3,900  vs 官网   4,700+        → 低 17%

如果观众数取自去展网、展商数取自官网，比值 = (真实×0.78) / 真实 = 凭空偏低 22%。
E1 的档位是按比值切的，20% 的偏移足以跨档。这种"半真半假"的比值比 unknown 更坏：
unknown 是诚实的，假数是误导。

所以本脚本只做一件事——**只给"两个数都缺"的展补，且两个数必须同源同时写入**。
只缺一个的展一律跳过：那一个数只能靠别的来源，混源不可接受。

## 匹配为什么要看城市和展期

只按名字匹配会撞车：
    "上海国际鞋展" vs "广州国际鞋展"
    "中国国际五金展" 每年两届 / 多地举办
去展网页面自带 `展会地点`（<a title="上海展会">）与 `<time datetime>` 展期，
用来交叉验证。城市不一致直接否决，年份差超 2 年降级。

地理信号有**两个**独立来源，都要查：
1. `city` 字段（95% 有值）
2. **标题里的地名**——剩下 5% 的空值只靠第 1 条会漏。
   实测：青岛的 SINOCES 曾以 0.88 分匹配到"深圳国际消费电子展览会"，
   名字几乎一样但根本不是同一个展，而那一行 `city` 恰好是空的。

## 三条否决规则（都是被真实错配打出来的）

1. **城市/地名冲突** → 否决。见上。
2. **观众/展商比超出 4~400** → 否决。佛山陶博会去展网给 60万/750 = 800 倍，
   展览面积才 30 万平米，物理上装不下 60 万人。这种数不是"特别好的展"，
   而是把历届累计人次当单届观众了。
3. **名称匹配分 < 0.80 或与第二名分差 < 0.05** → 不自动填。

## 落库

- expo 表：visitor_count / exhibitor_count / exhibit_area_sqm + 口径 + `scale_source="qufair"`
- expo_observation：三个字段各一条，source_type="thirdparty"、confidence="low"
- **不覆盖任何已有值**；写前逐个断言目标列为空

用法：
    python scripts/persona/match_qufair.py                 # 只出报告，不写库
    python scripts/persona/match_qufair.py --apply         # 写库
    python scripts/persona/match_qufair.py --min-score 0.9 # 提高匹配门槛
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "persona.db"
INDEX = ROOT / "data" / "batch4" / "qufair_index.json"
REPORT = ROOT / "data" / "batch4" / "match_report.csv"

# 名称归一时要剥掉的通用词。剥的是"所有展会都有的词"，不是"行业的词"——
# 剥行业词会把不同展合成一个，那是最坏的一类错误。
_GENERIC = (
    "中国", "国际", "全国", "全球", "世界", "亚洲", "亚太", "华夏",
    "展览会", "博览会", "展示交易会", "交易会", "展会", "展览", "展销会",
    "exhibition", "expo", "fair", "show", "china", "international",
    "global", "world", "asia", "the",
)
_BRACKET = re.compile(r"[（(][^)）]*[)）]")
_EDITION = re.compile(r"第\s*\d+\s*届")
_YEAR = re.compile(r"20\d{2}\s*年?")
_NONWORD = re.compile(r"[^0-9a-z\u4e00-\u9fff]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD = re.compile(r"[a-z]{2,}")

# 会展城市/国家名。用于从**原始**标题里嗅探地理信号——
# 括号里常写着举办地（"中国（北京）服务贸易交易会"），而 norm_name 会把括号整个剥掉，
# 所以必须在归一之前提取。这份表覆盖中国主要会展城市 + 常见海外举办国。
PLACES = (
    "北京", "上海", "广州", "深圳", "天津", "重庆", "杭州", "宁波", "温州", "义乌",
    "南京", "苏州", "无锡", "常州", "南通", "徐州", "扬州", "济南", "青岛", "烟台",
    "威海", "潍坊", "淄博", "临沂", "成都", "西安", "武汉", "长沙", "郑州", "洛阳",
    "合肥", "福州", "厦门", "南昌", "沈阳", "大连", "长春", "哈尔滨", "石家庄", "太原",
    "昆明", "贵阳", "南宁", "海口", "三亚", "兰州", "西宁", "银川", "乌鲁木齐", "拉萨",
    "佛山", "东莞", "中山", "珠海", "汕头", "惠州", "江门", "泉州", "晋江", "石狮",
    "嘉兴", "绍兴", "金华", "台州", "湖州", "莆田", "顺德", "南海",
    "香港", "澳门", "台北", "台湾",
    "美国", "英国", "德国", "法国", "日本", "韩国", "意大利", "西班牙", "俄罗斯",
    "印度", "巴西", "土耳其", "阿联酋", "迪拜", "沙特", "埃及", "南非", "澳大利亚",
    "加拿大", "墨西哥", "印尼", "印度尼西亚", "越南", "泰国", "马来西亚", "新加坡",
    "菲律宾", "波兰", "荷兰", "比利时", "瑞典", "瑞士", "奥地利", "希腊", "葡萄牙",
    "巴基斯坦", "孟加拉", "斯里兰卡", "尼泊尔", "缅甸", "柬埔寨", "老挝", "蒙古",
    "哈萨克斯坦", "乌兹别克斯坦", "以色列", "伊朗", "伊拉克", "卡塔尔", "科威特",
    "阿曼", "约旦", "黎巴嫩", "摩洛哥", "尼日利亚", "肯尼亚", "埃塞俄比亚",
    "加纳", "坦桑尼亚", "阿根廷", "智利", "秘鲁", "哥伦比亚", "委内瑞拉", "古巴",
    "新西兰", "爱尔兰", "丹麦", "挪威", "芬兰", "捷克", "匈牙利", "罗马尼亚",
    "保加利亚", "乌克兰", "白俄罗斯", "塞尔维亚", "克罗地亚", "斯洛伐克",
    "立陶宛", "拉脱维亚", "爱沙尼亚", "卢森堡", "冰岛", "摩纳哥",
)


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = _BRACKET.sub("", s)
    s = _EDITION.sub("", s)
    s = _YEAR.sub("", s)
    s = _NONWORD.sub("", s)
    for w in _GENERIC:
        s = s.replace(w, "")
    # 末尾单字"展"要单独剥：办展方一半写"XX展览会"一半写"XX展"，
    # 只剥整词"展览会"会让"西雅食品"和"西雅食品展"差一个字符，
    # 相似度从 0.88 掉到 0.55。只剥末尾，不动中间的"展"
    # （"展位""展馆"这类不能剥，剥了信息就没了）。
    return _TRAILING_ZHAN.sub("", s)


_TRAILING_ZHAN = re.compile(r"展$")


def place_of(title: str) -> str:
    """从原始标题嗅探举办地；多个命中取最先出现的那个。"""
    t = unicodedata.normalize("NFKC", title or "")
    hit = [(t.find(p), p) for p in PLACES if p in t]
    return min(hit)[1] if hit else ""


# 城市 → 省份。去展网有时把地点写成省（"浙江"）而不是市（"义乌"），
# 直接比前两个字会把它判成城市冲突——实测义乌小商品博览会就因此被错误否决。
# 同省不同市只判"中立"、不加分也不否决：广东一省就有广州家具展和东莞名家具展，
# 加了分反而会把它们混起来。
PROVINCE = {
    "浙江": "浙江", "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "义乌": "浙江",
    "嘉兴": "浙江", "绍兴": "浙江", "金华": "浙江", "台州": "浙江", "湖州": "浙江",
    "永康": "浙江",
    "广东": "广东", "广州": "广东", "深圳": "广东", "佛山": "广东", "东莞": "广东",
    "中山": "广东", "珠海": "广东", "汕头": "广东", "惠州": "广东", "江门": "广东",
    "顺德": "广东", "南海": "广东", "潮州": "广东", "揭阳": "广东",
    "江苏": "江苏", "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏",
    "南通": "江苏", "徐州": "江苏", "扬州": "江苏", "泰州": "江苏", "镇江": "江苏",
    "盐城": "江苏",
    "山东": "山东", "济南": "山东", "青岛": "山东", "烟台": "山东", "威海": "山东",
    "潍坊": "山东", "淄博": "山东", "临沂": "山东", "济宁": "山东", "泰安": "山东",
    "德州": "山东",
    "福建": "福建", "福州": "福建", "厦门": "福建", "泉州": "福建", "晋江": "福建",
    "石狮": "福建", "莆田": "福建", "漳州": "福建",
    "河北": "河北", "石家庄": "河北", "唐山": "河北", "保定": "河北", "邯郸": "河北",
    "廊坊": "河北",
    "辽宁": "辽宁", "沈阳": "辽宁", "大连": "辽宁",
    "吉林": "吉林", "长春": "吉林",
    "黑龙江": "黑龙江", "哈尔滨": "黑龙江", "大庆": "黑龙江",
    "四川": "四川", "成都": "四川", "绵阳": "四川",
    "湖北": "湖北", "武汉": "湖北", "宜昌": "湖北",
    "湖南": "湖南", "长沙": "湖南", "株洲": "湖南",
    "河南": "河南", "郑州": "河南", "洛阳": "河南", "漯河": "河南", "驻马店": "河南",
    "安徽": "安徽", "合肥": "安徽", "芜湖": "安徽",
    "江西": "江西", "南昌": "江西",
    "陕西": "陕西", "西安": "陕西",
    "山西": "山西", "太原": "山西",
    "云南": "云南", "昆明": "云南",
    "贵州": "贵州", "贵阳": "贵州",
    "广西": "广西", "南宁": "广西", "桂林": "广西",
    "海南": "海南", "海口": "海南", "三亚": "海南",
    "甘肃": "甘肃", "兰州": "甘肃", "青海": "青海", "西宁": "青海",
    "宁夏": "宁夏", "银川": "宁夏", "新疆": "新疆", "乌鲁木齐": "新疆",
    "西藏": "西藏", "拉萨": "西藏", "内蒙古": "内蒙古", "呼和浩特": "内蒙古",
    "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
}


def province_of(place: str) -> str:
    return PROVINCE.get((place or "")[:2], "")


def _split_cjk_ascii(s: str) -> tuple[str, str]:
    """把归一后的名字拆成"中文字段"和"英文词序列"。
    "门窗幕墙fenestrationbauchina" 的问题是英文尾巴把中文主体的相似度稀释掉了，
    分开比能各自算各自的。"""
    cjk = "".join(_CJK.findall(s or ""))
    # 英文部分要还原成词再拼，否则 "bauchina" 这种连写 bigram 没有意义
    en = "".join(_ASCII_WORD.findall(s or ""))
    return cjk, en


def bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}


def _sim_one(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    # 包含关系给 0.88。两个约束都是被真实错配逼出来的：
    # - 比例 0.45 而不是 0.6：办展方常给名字加限定语（"食品和饮料" vs "食品"），
    #   这是同一个展的改写不是另一个展。SIAL 那条实测卡在 0.545。
    # - 短串至少 5 个字符：否则 "消费电子" 4 字就能靠包含"巴基斯坦消费电子"拿 0.88，
    #   "健康产业" 靠包含"广州妇幼健康产业"拿 0.88 —— 全是不同的展。
    #   名字剥完通用词只剩 4 个字的，本来就没有足够信息判定同一性。
    if len(short) >= 5 and short in long and len(short) / len(long) >= 0.45:
        return 0.88
    ga, gb = bigrams(a), bigrams(b)
    if not ga or not gb:
        return 0.0
    return round(len(ga & gb) / len(ga | gb) * 0.85, 3)


def similarity(a: str, b: str) -> float:
    """整体相似度 = max(整体比, 纯中文比)。
    整体比能吃掉"中文完全一致 + 英文不同"的情况；
    纯中文比专门救"英文名被写进中文名"（FENESTRATION BAU CHINA）。"""
    s = _sim_one(a, b)
    ca, cb = _split_cjk_ascii(a)[0], _split_cjk_ascii(b)[0]
    if ca and cb and (ca, cb) != (a, b):
        s = max(s, _sim_one(ca, cb))
    return s


def _year_of(iso: str | None) -> int | None:
    try:
        return int(str(iso)[:4])
    except (TypeError, ValueError):
        return None


def score(expo: dict, cand: dict) -> tuple[float, list[str]]:
    """返回 (分数, 否决/降级理由)。"""
    why: list[str] = []
    s = similarity(norm_name(expo["name_cn"]), norm_name(cand["title"]))
    if expo.get("name_en"):
        s = max(s, similarity(norm_name(expo["name_en"]), norm_name(cand["title"])) * 0.9)
    if s <= 0:
        return 0.0, ["名称无重合"]

    # 城市交叉验证：有冲突直接否决。这是挡住"上海鞋展/广州鞋展"唯一有效的手段
    ec, qc = (expo.get("city") or ""), (cand.get("city") or "")
    if ec and qc:
        if ec[:2] == qc[:2]:
            s = min(1.0, s + 0.05)
        elif province_of(ec) and province_of(ec) == province_of(qc):
            pass  # 同省不同市（义乌 vs 浙江 / 广州 vs 广东），中立
        else:
            return 0.0, [f"城市冲突 {ec} vs {qc}"]

    # 城市嗅探兜底：去展网 city 有 5% 是空的，空的就躲过了上面那道检查。
    # 例子：青岛的"中国国际消费电子博览会"（SINOCES）曾以 0.88 分匹配到
    # "深圳国际消费电子展览会"——名字几乎一样，但不是同一个展。
    # 标题里的地名是独立于 city 字段的第二个证据源。
    if ec:
        qp = place_of(cand["title"])
        if qp and qp[:2] != ec[:2] and not (
                province_of(ec) and province_of(ec) == province_of(qp)):
            return 0.0, [f"标题地名冲突 {ec} vs {qp}"]

    ey, qy = _year_of(expo.get("start_date")), cand.get("year") or _year_of(cand.get("start_date"))
    if ey and qy:
        d = abs(ey - qy)
        if d >= 3:
            return 0.0, [f"年份差 {d} 年"]
        if d >= 2:
            s -= 0.1
            why.append(f"年份差 {d} 年")
    return round(s, 3), why


# 观众/展商比的物理边界。这个区间来自 persona.db 里 35 个能算比值的真展：
# 归一后 P25=25.4 / P50=40.0 / P75=73.3，几乎全部落在 5~300。
# 超出这个范围的不是"特别好的展"，而是口径错（累计人次）或展商数漏抄。
# 实例：佛山陶博会 去展网给 60万观众 / 750 展商 = 800 倍，比值一比就知道有问题。
RATIO_MIN, RATIO_MAX = 4.0, 400.0


def sanity(cand: dict) -> str:
    """返回不通过的原因，通过则返回空串。"""
    v, e = cand.get("visitors") or 0, cand.get("exhibitors") or 0
    if not v or not e:
        return "缺数"
    r = v / e
    if not (RATIO_MIN <= r <= RATIO_MAX):
        return "比值 %.0f 超出 %g~%g" % (r, RATIO_MIN, RATIO_MAX)
    return ""


def load_expos(con: sqlite3.Connection) -> list[dict]:
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(
        "SELECT id, slug, name_cn, name_en, city, start_date,"
        " visitor_count, exhibitor_count, exhibit_area_sqm, scale_source FROM expo")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--min-score", type=float, default=0.8)
    ap.add_argument("--gap", type=float, default=0.05,
                    help="第一名与第二名的最小分差；低于此值视为有歧义，不自动填")
    args = ap.parse_args()

    if not INDEX.exists():
        print("✗ 没有 %s，先跑 collect_qufair.py" % INDEX, file=sys.stderr)
        return 2
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    raw = [v for v in idx.values()
           if not v.get("error") and v.get("visitors") and v.get("exhibitors")]
    cands, bad = [], []
    for v in raw:
        why = sanity(v)
        if why:
            bad.append((why, v))
        else:
            cands.append(v)
    print("去展网可用条目 %d / %d" % (len(cands), len(idx)))
    if bad:
        print("  剔除比值异常 %d 条（口径错或漏抄，宁缺毋滥）：" % len(bad))
        for why, v in bad[:8]:
            print("    %-42s 观众%-9s 展商%-7s %s" % (
                v["title"][:42], v["visitors"], v["exhibitors"], why))
        if len(bad) > 8:
            print("    …… 余 %d 条" % (len(bad) - 8))

    con = sqlite3.connect(DB)
    expos = load_expos(con)

    rows, todo = [], []
    veto_stat: dict[str, int] = {}
    for e in expos:
        ranked, vetoed = [], []
        for c in cands:
            s, why = score(e, c)
            if s > 0:
                ranked.append((s, c, why))
            else:
                r = why[0] if why else "未知"
                # 把具体城市名抹掉再聚合，否则"城市冲突 上海 vs 北京"这种
                # 每条都不一样，统计出来是一堆 1 次的噪声
                key = r.split(" ")[0]
                veto_stat[key] = veto_stat.get(key, 0) + 1
                vetoed.append(r)
        ranked.sort(key=lambda x: -x[0])
        best = ranked[0] if ranked else None
        second = ranked[1] if len(ranked) > 1 else None

        both_missing = not e["visitor_count"] and not e["exhibitor_count"]
        row = {
            "slug": e["slug"], "name_cn": e["name_cn"], "city": e["city"] or "",
            "has_v": int(bool(e["visitor_count"])), "has_e": int(bool(e["exhibitor_count"])),
            "qufair_title": best[1]["title"] if best else "",
            "qufair_city": (best[1].get("city") or "") if best else "",
            "score": best[0] if best else 0,
            "second": second[0] if second else "",
            "q_visitors": best[1]["visitors"] if best else "",
            "q_exhibitors": best[1]["exhibitors"] if best else "",
            "q_area": (best[1].get("area") or "") if best else "",
            "q_year": (best[1].get("year") or "") if best else "",
            "n_veto": len(vetoed),
            "veto": "；".join(sorted(set(vetoed))[:3]),
            "decision": "", "reason": "",
        }

        if not both_missing:
            row["decision"] = "skip_has_one"
            row["reason"] = "已有一个数，混源不可接受"
        elif not best or best[0] < args.min_score:
            row["decision"] = "skip_low_score"
            row["reason"] = "无匹配或低于门槛 %.2f" % args.min_score
        elif second and (best[0] - second[0]) < args.gap:
            row["decision"] = "skip_ambiguous"
            row["reason"] = "与第二名分差 %.3f < %.2f" % (best[0] - second[0], args.gap)
        else:
            row["decision"] = "fill"
            row["reason"] = "｜".join(best[2]) or "ok"
            todo.append((e, best[1], best[0]))
        rows.append(row)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    stat: dict[str, int] = {}
    for r in rows:
        stat[r["decision"]] = stat.get(r["decision"], 0) + 1
    print("\n匹配结果：" + " ｜ ".join(f"{k}={v}" for k, v in sorted(stat.items())))
    if veto_stat:
        print("否决原因分布：" + " ｜ ".join(
            f"{k}={v}" for k, v in sorted(veto_stat.items(), key=lambda x: -x[1])[:6]))
    print("\n将被填充的展（两个数都缺 + 匹配唯一）：")
    for e, c, s in sorted(todo, key=lambda x: -x[2]):
        print("  %-20s %5.2f  %-28s  %s → 观众 %s / 展商 %s" % (
            e["slug"], s, c["title"][:28], c.get("city") or "-",
            c["visitors"], c["exhibitors"]))

    print("\n报告 → %s" % REPORT)
    if not args.apply:
        print("\n未写库（加 --apply 执行）。")
        return 0
    if not todo:
        print("没有可填的展。")
        return 0

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = con.cursor()
    cur.execute(
        "INSERT INTO import_batch (filename, row_count, inserted, updated, skipped, failed,"
        " operator, note, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("qufair_index.json", len(rows), 0, len(todo), len(rows) - len(todo), 0,
         "match_qufair", "去展网第三方规模数据补采（成对）", now))
    batch_id = cur.lastrowid

    n = 0
    for e, c, s in todo:
        # 写前再断言一次目标列为空。前面已经筛过，但这一步是最后一道防线：
        # 断言失败的代价是覆盖掉官网一手数据，不可逆。
        cur.execute("SELECT visitor_count, exhibitor_count FROM expo WHERE id=?", (e["id"],))
        v, ex = cur.fetchone()
        assert not v and not ex, "目标列已被填充，拒绝覆盖：%s" % e["slug"]
        assert not sanity(c), "比值不健全：%s %s" % (e["slug"], sanity(c))

        cur.execute(
            "UPDATE expo SET visitor_count=?, visitor_caliber='person', visitor_count_raw=?,"
            " exhibitor_count=?, exhibitor_caliber='company',"
            " exhibit_area_sqm=?, area_caliber='gross', scale_source='qufair',"
            " updated_at=? WHERE id=?",
            (c["visitors"], "%s 观众数量" % c["visitors"],
             c["exhibitors"], c.get("area") or None, now, e["id"]))
        for key, val, raw, unit, cal in (
            ("visitor_count", c["visitors"], "观众数量：%s人" % c["visitors"], "人", "person"),
            ("exhibitor_count", c["exhibitors"], "展商数量：%s家" % c["exhibitors"], "家", "company"),
            ("area", c.get("area"), "展览面积：%s平方米" % c.get("area"), "㎡", "gross"),
        ):
            if not val:
                continue
            cur.execute(
                "INSERT OR REPLACE INTO expo_observation (expo_id, field_key, raw_text,"
                " num_value, unit, caliber, source_url, source_type, fetched_at,"
                " confidence, batch_id, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (e["id"], key, raw, float(val), unit, cal, c["url"], "thirdparty",
                 now, "low", batch_id, now))
        n += 1

    con.commit()
    print("\n✓ 写入 %d 个展；batch_id=%d" % (n, batch_id))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
