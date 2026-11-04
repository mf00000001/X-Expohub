"""
自然语言查询解析（输入框替用户把话补全）

## 为什么需要这一层

用户不会按数据库字段说话。他不会输入"primary_category=医药及医疗保健&city=上海"，
他说的是"我要参加 11 月的上海医疗器械展，预算 8 万"。

把这句话拆成可筛选的结构化条件，是这一层的全部职责。
**界面上必须先回显"我被理解成了什么"**，用户才有动力纠正——
如果解析错了却直接给结果，用户只会觉得"这系统搜不准"，而不知道该改哪里。

## 三条设计原则

1. **抽不出就置「未提供」，绝不猜。**
   "预算 8 万"能抽；"便宜点的展"不能抽成 1 万元——那是我编的。
   空着的 chip 是灰色虚线框，用户点一下就能填，比填一个错的强。

2. **抽错了也能用。**
   不追求 100% 抽取率。抽到 4 个条件就能筛，抽到 1 个也能按那 1 个筛。
   解析失败不能阻断流程——最差情况是用户看到 6 个"未提供"，
   手动点两下就补齐了。

3. **每个 chip 带 evidence。**
   用户问"为什么识别成上海"，要能回答"因为句子里出现了『上海』"。
   没有 evidence 的解析结果，用户没法验证，也就没法信任。

## 为什么是规则而不是 LLM

规则可测、可解释、零延迟、零成本。这 6 个字段的取值空间是封闭的
（城市表、18 品类、月份、预算量级），规则覆盖率足够。
LLM 兜底留给"整句向量检索"—— 那是语义召回，不是字段抽取，
两者解决的问题不同，不该混在一起。

对应截图："前端五种引导 + 后端规则化归一 + 失败兜底"
"""

from __future__ import annotations

import re
from typing import Optional

# ============================================================
# 词表
# ============================================================

# 城市 → 常见别名。「沪/京/穗/深」这种单字太容易误伤（"深"在"深度"里），
# 只收不会出现在普通词里的写法。
CITY_WORDS: dict[str, list[str]] = {
    "上海": ["上海", "沪上"],
    "北京": ["北京", "京城"],
    "广州": ["广州", "羊城"],
    "深圳": ["深圳", "鹏城"],
    "杭州": ["杭州"],
    "南京": ["南京"],
    "成都": ["成都"],
    "重庆": ["重庆"],
    "武汉": ["武汉"],
    "西安": ["西安"],
    "青岛": ["青岛"],
    "宁波": ["宁波"],
    "厦门": ["厦门"],
    "苏州": ["苏州"],
    "无锡": ["无锡"],
    "东莞": ["东莞", "虎门"],
    "佛山": ["佛山"],
    "中山": ["中山", "古镇"],
    "义乌": ["义乌"],
    "永康": ["永康"],
    "温州": ["温州"],
    "晋江": ["晋江"],
    "南宁": ["南宁"],
    "海口": ["海口"],
    "郑州": ["郑州"],
    "天津": ["天津"],
    "香港": ["香港"],
    "合肥": ["合肥"],
    "济南": ["济南"],
    "昆明": ["昆明"],
    "福州": ["福州"],
    "长沙": ["长沙"],
    "沈阳": ["沈阳"],
}

# 品类关键词。左边是 18 品类（与 app/models/category.py 逐字一致），
# 右边是用户可能说的词。
#
# 排序有讲究：匹配时按**词长降序**，所以"医疗器械"会先于"医疗"命中，
# 避免"汽车配件"被"汽车"抢走。"配件"归车辆及配件，"零部件"也是。
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "医药及医疗保健": ["医疗器械", "医疗", "医药", "药品", "制药", "口腔", "牙科",
                  "保健品", "医院", "诊断", "生物医药", "原料药"],
    "机械": ["激光切割机", "激光", "机床", "机械", "数控", "工业设备", "机器人",
             "塑料机械", "橡塑", "包装机械", "印刷", "铸造", "焊接"],
    "车辆及配件": ["汽车配件", "汽车零部件", "零部件", "汽配", "汽车", "车展",
              "商用车", "新能源车", "轮胎", "摩托车", "电动车"],
    "电子及家电": ["消费电子", "电子元器件", "家电", "电器", "电子", "半导体",
              "集成电路", "芯片", "PCB", "电路板", "连接器"],
    "五金工具": ["五金", "工具", "紧固件", "轴承", "刃具", "磨料", "锁具"],
    "建材": ["建材", "建筑装饰", "门窗", "幕墙", "陶瓷", "卫浴", "石材", "涂料",
           "防水", "吊顶", "地板"],
    "化工产品": ["化工", "胶粘剂", "密封剂", "精细化工", "树脂", "助剂", "颜料",
             "化学品", "油墨"],
    "能源": ["光伏", "储能", "氢能", "风电", "风能", "太阳能", "新能源", "电池",
           "电力", "石油", "石化", "天然气"],
    "日用消费品": ["日用百货", "消费品", "日用品", "家居用品", "小商品", "母婴",
              "孕婴童", "宠物", "清洁用品", "塑料制品"],
    "礼品": ["礼品", "赠品", "促销品", "工艺品", "文创", "节庆用品", "家居礼品"],
    "纺织服装": ["面料", "辅料", "纺织", "服装", "服饰", "家纺", "针织", "纱线",
             "纺织机械"],
    "鞋类": ["鞋材", "鞋机", "鞋业", "皮鞋", "运动鞋", "鞋"],
    "家居装饰品": ["家具", "家居装饰", "软装", "灯饰家居", "家饰", "装饰画",
              "地毯", "窗帘"],
    "办公箱包及休闲用品": ["文具", "办公用品", "箱包", "手袋", "皮具", "户外用品",
                   "露营", "休闲运动", "体育用品", "健身"],
    "食品": ["食品", "饮料", "咖啡", "茶", "烘焙", "焙烤", "酒", "调味品",
           "食材", "餐饮", "冰淇淋", "糖果"],
    "照明": ["照明", "灯具", "灯饰", "LED", "灯光"],
    "AI/科技": ["人工智能", "AI", "大数据", "云计算", "物联网", "智慧城市",
              "软件", "信息技术", "数字经济", "元宇宙"],
    "综合服务": ["物流", "供应链", "跨境电商", "电商", "零售", "服务贸易",
             "加盟", "特许经营", "教育", "金融", "会展服务", "人力资源"],
}

MONTH_WORDS: dict[str, tuple[int, int]] = {
    "一月": (1, 1), "二月": (2, 2), "三月": (3, 3), "四月": (4, 4),
    "五月": (5, 5), "六月": (6, 6), "七月": (7, 7), "八月": (8, 8),
    "九月": (9, 9), "十月": (10, 10), "十一月": (11, 11), "十二月": (12, 12),
    "春季": (3, 5), "夏天": (6, 8), "夏季": (6, 8), "秋季": (9, 11),
    "冬天": (12, 2), "冬季": (12, 2),
    "上半年": (1, 6), "下半年": (7, 12),
    "年初": (1, 3), "年底": (10, 12), "年末": (10, 12),
}

SCALE_WORDS: dict[str, tuple[str, str]] = {
    "large": ("大展", "国际大展、行业标杆级"),
    "mid": ("中等规模", "区域性专业展"),
    "small": ("小展", "垂类或地方展"),
}

# chip 的展示顺序和标签。顺序来自截图：行业 → 品类 → 地域 → 预算 → 数量 → 交期。
# 我们场景里"数量/交期"换成"时间/规模"：参展的人关心"什么时候办""这展多大"，
# 不关心采购数量。
CHIP_SPECS: list[dict] = [
    {"key": "industry", "label": "行业", "hint": "你说的那个词，原样保留"},
    {"key": "category", "label": "品类", "hint": "归到 18 个标准品类之一，决定怎么筛"},
    {"key": "city", "label": "地域", "hint": "举办城市"},
    {"key": "month", "label": "时间", "hint": "想看几月的展"},
    {"key": "budget", "label": "预算", "hint": "展位预算（万元）"},
    {"key": "scale", "label": "规模", "hint": "大展还是垂类小展"},
]


# ============================================================
# 抽取
# ============================================================

def _find_city(text: str) -> tuple[Optional[str], Optional[str]]:
    """返回 (城市, 命中的原文)。"""
    best: tuple[str, str] | None = None
    for city, words in CITY_WORDS.items():
        for w in words:
            pos = text.find(w)
            if pos >= 0:
                if best is None or len(w) > len(best[1]):
                    best = (city, w)
    return (best[0], best[1]) if best else (None, None)


def _find_category(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    返回 (品类, 命中的原始词, 行业词)。

    行业词和品类的关系：用户说"激光切割机"，行业词是"激光切割机"（原样），
    品类是"机械"（上位归类）。界面上一行显示两个 chip，
    用户能看出"我说的是激光切割机，它归到了机械"——归错了一眼能发现。
    """
    hits: list[tuple[int, str, str]] = []   # (词长, 品类, 词)
    for cat, words in CATEGORY_KEYWORDS.items():
        for w in words:
            if w in text:
                hits.append((len(w), cat, w))

    if not hits:
        return None, None, None

    # 最长匹配优先：避免"汽车"抢走"汽车配件"
    hits.sort(key=lambda x: -x[0])
    _, cat, word = hits[0]
    return cat, word, word


def _find_month(text: str) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """返回 (起月, 止月, 原文)。"""
    # 阿拉伯数字："11月" / "11 月份"
    m = re.search(r"(\d{1,2})\s*月", text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 12:
            return n, n, m.group(0).strip()

    best: tuple[int, int, str] | None = None
    for w, (lo, hi) in MONTH_WORDS.items():
        if w in text and (best is None or len(w) > len(best[2])):
            best = (lo, hi, w)
    return (best[0], best[1], best[2]) if best else (None, None, None)


def _find_budget(text: str) -> tuple[Optional[float], Optional[str]]:
    """
    返回 (万元, 原文)。

    只认带"预算/费用/花费"上下文的数字，或者带"万/w"单位的。
    裸数字不认——"我要 3 个展位"里的 3 不是预算。
    """
    patterns = [
        r"(?:预算|费用|花费|投入|准备花)\D{0,6}?(\d+(?:\.\d+)?)\s*(万|w|W|千|k|K)?",
        r"(\d+(?:\.\d+)?)\s*(?:万元|万块|w|W)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        value = float(m.group(1))
        unit = (m.group(2) or "万").lower() if m.lastindex and m.lastindex >= 2 else "万"
        if unit in ("千", "k"):
            value = value / 10.0      # 8000千元 = 800万元，千元→万元除以 10
        # 只带数字没单位、又不是"预算"引导的，忽略
        if m.lastindex and m.lastindex < 2 and "预算" not in m.group(0):
            continue
        if not (0 < value <= 5000):
            continue
        return round(value, 1), m.group(0).strip()
    return None, None


def _find_scale(text: str) -> tuple[Optional[str], Optional[str]]:
    large = ["大展", "大型", "标杆", "头部", "国际大展", "知名展", "规模大"]
    small = ["小展", "中小", "垂类", "细分", "地方展", "小众"]
    mid = ["中等", "区域展", "腰部"]

    for words, key in ((large, "large"), (small, "small"), (mid, "mid")):
        for w in words:
            if w in text:
                return key, w
    return None, None


def _chip(
    key: str,
    label: str,
    provided: bool,
    value,
    display: str,
    evidence: Optional[str] = None,
    **extra,
) -> dict:
    """
    统一的 chip 结构。

    `provided=False` 时 **value 必须是 None**——不能让调用方拿到一个
    "未提供但值为 0" 的 chip 然后拿 0 去筛选。这是"漏填不等于满足"的同一个坑：
    E5 里漏填按 unknown 处理，这里漏抽必须是 None。
    """
    assert not provided or value is not None, f"chip {key} 标记为已提供但没有值"
    return {
        "key": key,
        "label": label,
        "provided": provided,
        "value": value if provided else None,
        "display": display,
        "evidence": evidence,
        **extra,
    }


def parse_query(text: str) -> dict:
    """
    把一句话拆成 6 个 chip。

    返回值：
        chips: 6 个 chip，顺序固定（与界面一致）
        filters: 可直接拼进 /expos 查询参数的对象（只含有值的项）
        understood: 抽到了几个条件（用于界面提示"识别到 4 个条件"）
        unmatched: 没抽到的 chip 的标签，界面用来引导用户补
    """
    raw = (text or "").strip()
    chips: list[dict] = []

    if not raw:
        for spec in CHIP_SPECS:
            chips.append(_chip(spec["key"], spec["label"], False, None, "未提供"))
        return {
            "query": raw,
            "chips": chips,
            "filters": {},
            "understood": 0,
            "unmatched": [c["label"] for c in chips],
        }

    # 行业：优先取命中的品类关键词（"激光切割机"），否则不填
    cat, word, industry_word = _find_category(raw)
    industry = _chip(
        "industry", "行业",
        industry_word is not None,
        industry_word,
        industry_word or "未提供",
        industry_word,
    )

    # 品类：带可选项，前端点开能改
    category = _chip(
        "category", "品类",
        cat is not None,
        cat,
        cat or "未提供",
        word,
        options=sorted(CATEGORY_KEYWORDS.keys()),
    )

    city, city_word = _find_city(raw)
    city_chip = _chip(
        "city", "地域",
        city is not None,
        city,
        city or "未提供",
        city_word,
        options=sorted(CITY_WORDS.keys()),
    )

    m_lo, m_hi, m_word = _find_month(raw)
    month_value = None
    if m_lo is not None:
        month_value = m_lo if m_lo == m_hi else {"from": m_lo, "to": m_hi}
    month_display = "未提供"
    if m_lo is not None:
        month_display = f"{m_lo} 月" if m_lo == m_hi else f"{m_lo}–{m_hi} 月"
    month = _chip(
        "month", "时间",
        m_lo is not None,
        month_value,
        month_display,
        m_word,
    )

    budget_value, budget_word = _find_budget(raw)
    budget = _chip(
        "budget", "预算",
        budget_value is not None,
        budget_value,
        f"{budget_value:g} 万元" if budget_value is not None else "未提供",
        budget_word,
    )

    scale_value, scale_word = _find_scale(raw)
    scale = _chip(
        "scale", "规模",
        scale_value is not None,
        scale_value,
        SCALE_WORDS[scale_value][0] if scale_value else "未提供",
        scale_word,
    )

    chips = [industry, category, city_chip, month, budget, scale]

    # ---- 拼筛选条件 ----
    filters: dict = {}
    if cat:
        filters["category"] = cat
    if city:
        filters["city"] = city
    if m_lo is not None:
        filters["month_from"] = m_lo
        filters["month_to"] = m_hi
    if scale_value:
        filters["scale"] = scale_value
    # 预算暂不参与筛选：展位价 0/94 齐全，没有价格就没法按预算筛。
    # 硬筛会筛出空结果，比不筛更糟。它在详情页的 E3 里作为参照出现。

    unmatched = [c["label"] for c in chips if not c["provided"]]
    return {
        "query": raw,
        "chips": chips,
        "filters": filters,
        "understood": sum(1 for c in chips if c["provided"]),
        "unmatched": unmatched,
        "note": "预算暂不参与筛选：展位价格暂无公开数据（0/94）；"
                "时间筛选只对有开展日期的展生效，无日期的展排在结果末尾并标注。",
    }


# ============================================================
# 自检
# ============================================================

def self_check() -> list[str]:
    issues: list[str] = []

    r = parse_query("我要参加 11 月的上海医疗器械展，预算 8 万")
    got = {c["key"]: c for c in r["chips"]}
    if got["city"]["value"] != "上海":
        issues.append(f"地域应为上海，实际 {got['city']['value']}")
    if got["category"]["value"] != "医药及医疗保健":
        issues.append(f"品类应为医药及医疗保健，实际 {got['category']['value']}")
    if got["industry"]["value"] != "医疗器械":
        issues.append(f"行业应为医疗器械，实际 {got['industry']['value']}")
    if got["month"]["value"] != 11:
        issues.append(f"月份应为 11，实际 {got['month']['value']}")
    if got["budget"]["value"] != 8.0:
        issues.append(f"预算应为 8.0 万，实际 {got['budget']['value']}")
    if got["scale"]["provided"]:
        issues.append("没提规模却识别出了规模")

    # 模糊表述不能瞎猜
    r2 = parse_query("找个便宜点的展")
    got2 = {c["key"]: c for c in r2["chips"]}
    if got2["budget"]["provided"]:
        issues.append("「便宜点的展」不该抽出预算数字")
    if any(c["provided"] for c in r2["chips"]):
        issues.append(f"「{r2['query']}」不该抽出任何条件，实际抽到 "
                      f"{[c['key'] for c in r2['chips'] if c['provided']]}")

    # 最长匹配：汽车配件不能被"汽车"抢
    r3 = parse_query("上海汽车配件展")
    got3 = {c["key"]: c for c in r3["chips"]}
    if got3["industry"]["value"] != "汽车配件":
        issues.append(f"行业应识别为汽车配件，实际 {got3['industry']['value']}")

    # 空输入
    r4 = parse_query("")
    if r4["understood"] != 0:
        issues.append("空输入应识别出 0 个条件")

    # 年度区间
    r5 = parse_query("下半年北京的工业展")
    got5 = {c["key"]: c for c in r5["chips"]}
    if got5["month"]["value"] != {"from": 7, "to": 12}:
        issues.append(f"下半年应解析为 7-12 月，实际 {got5['month']['value']}")

    # 未提供必须是 None，不能是 0 / 空串
    for c in r2["chips"]:
        if not c["provided"] and c["value"] is not None:
            issues.append(f"chip {c['key']} 未提供但值是 {c['value']!r}")

    return issues
