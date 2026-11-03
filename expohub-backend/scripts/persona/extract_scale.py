"""
批次 2：规模与属性字段抽取（观众数、展商数、面积、上届规模、观众准入、展会性质）。

与批次 1 的根本区别：**这批是数值字段，光有数字没用，必须带口径。**

  "30 万" 是人次还是人数？差 2~3 倍。
  "2500 家" 是企业数还是品牌数？差 1.5 倍。
  "30 万平方米" 是净面积还是毛面积？差 40%。

所以每个数值字段落库时都要带三件套：`raw_text`（原文）、`value`（算出来的数）、
`caliber`（口径）。只存一个整数，100 个展算出来的分位全是幻觉。

核验（防幻觉）的做法也与批次 1 不同：
批次 1 是"依据里能不能找到这个字符串"，这批是"**这个数能不能从依据里算出来**"。
模型给 300000，依据写"超 30 万人次"——数字串对不上，必须解析"30 万"再比。

用法：
    python scripts/persona/extract_scale.py --dry-run
    python scripts/persona/extract_scale.py
    python scripts/persona/extract_scale.py --reverify     # 改了核验规则后离线重跑
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BATCH2 = ROOT / "data" / "batch2"
OUT = BATCH2 / "scale.json"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.modules.ai.llm import OpenAICompatProvider, _build_real_provider  # noqa: E402
from llm_extract import (  # noqa: E402
    SUB_DIR, _flat, _json_of, _norm_sep, _slices, all_ids, load_body,
)

FIELDS = ("visitor_count", "exhibitor_count", "exhibition_area",
          "prev_visitor_count", "prev_exhibitor_count", "prev_area",
          "admission", "nature")

SYSTEM = ("你是展会数据抽取器。只做抽取，不做推测。"
          "输出必须是单个 JSON 对象，不要 markdown 代码块，不要解释。")

# 规模数据不在首屏，在页面中后段的"展会规模 / Fair Statistics / 上届回顾"里。
# 用日期那套关键词（截止/主办）去找规模，等于没找。
SCALE_KWS = ("观众", "买家", "参展商", "展出面积", "平方米", "展位", "上届", "往届",
             "规模", "统计", "人次", "仅限", "专业观众", "预登记", "门票", "入场",
             "Visitor", "visitor", "Exhibitor", "exhibitor", "Statistics", "statistics",
             "sqm", "square meters", "attendees", "Buyers", "registration", "Trade")

PROMPT = """从展会网页正文中抽取规模与属性字段。**只抽文中明确写出的数字，绝不估算或推算。**

输出 JSON，每个字段格式为 {"value":..., "raw_text":"...", "unit":"...", "caliber":"...", "evidence":"..."}
· evidence 必须是正文里**逐字出现**的一段原文（10~80 字）
· raw_text 是含数字的那一小段原文（如"超30万人次"）
· 找不到依据的字段，value 给 null，其余给空串

【A 组：最近一届规模——有数就填，不要因为没标"本届/上届"就留空】
1. visitor_count —— 观众数量，**绝对值整数**
   · "30万" 写 300000，"12.5万" 写 125000，"79,026" 写 79026，"12.5K" 写 12500
   · 英文站同样处理：原文 "79,026 professional visitors" → 79026
   caliber 只能取："visit"（人次）/ "person"（人数）/ "registered"（注册数）/ "unknown"
   · 原文写"人次"就是 visit；写"人""名""visitors"就是 person
2. exhibitor_count —— 参展商数量，整数
   · 原文只给"展位数"或"品牌数"也填，但 caliber 必须是 "booth" / "brand"
   caliber："company"（企业数）/ "brand"（品牌数）/ "booth"（展位数）/ "unknown"
3. exhibition_area —— 展览面积，单位平方米，整数
   caliber："net"（净面积）/ "gross"（毛面积或未注明）
4. 这三个字段填页面给出的**最新一届**规模：不管是本届、刚结束的一届，
   还是页面标注为"上届"的那一届——**只要它是页面上最新的一届，就填这里**。
   页面只有一个规模数字且没标届次，同样填这里。

【B 组：对比基线——只在能分清两届时填】
5. prev_visitor_count / prev_exhibitor_count / prev_area
   · 只有当页面**同时**给出两届数字、且能分清哪届新哪届旧时才填
   · 只有一个数 → 一律留空。**不要把 A 组的数复制到 prev_***

【C 组：属性】
6. admission —— 观众准入类型：
   "trade_only"（仅专业人士）/ "public"（向公众开放）/ "mixed"（前几日专业、后几日公众）
   · 依据可以是登记要求（需营业执照/名片/审核/预登记 → trade_only）、
     票务信息（可购票/售票/欢迎市民 → public）、
     或专业侧与公众侧同时出现（"专业观众日""公众开放日" → mixed）
   · 这些都没有才填 null。不要用品牌口号、展会愿景、导航菜单充当依据。
7. nature —— 展会性质："B2B" / "B2C" / "mixed"
   · 依据要能看出买家构成：专业买家/采购商/批发/出口 → B2B；
     终端消费者/零售/市民 → B2C；两者兼有 → mixed。看不出就 null。

【这几种情况即使有数字也不要填】
· 年度累计、多展合计、集团全球数据（"全年 8000+ 企业参展""SIAL in China 55,000 exhibitors"）
· 峰会/论坛/同期活动/线上直播的参与人数
· 展商名录收录条数（"Total Result 1714"）、展馆数量
· 预测值、目标值（"预计""力争""有望"）
· 其他城市、其他子展的数据（本页讲上海展，就别用广州展的数）

另外附一个 text_note 字符串，写你在口径上拿不准的地方（没有就给空串）。

输出格式示例：
{"visitor_count":{"value":300000,"raw_text":"超30万人次","unit":"人次","caliber":"visit","evidence":"..."},
 "exhibitor_count":{"value":null,"raw_text":"","unit":"","caliber":"","evidence":""},
 "exhibition_area":{"value":null,"raw_text":"","unit":"","caliber":"","evidence":""},
 "prev_visitor_count":{"value":null,"raw_text":"","unit":"","caliber":"","evidence":""},
 "prev_exhibitor_count":{"value":null,"raw_text":"","unit":"","caliber":"","evidence":""},
 "prev_area":{"value":null,"raw_text":"","unit":"","caliber":"","evidence":""},
 "admission":{"value":null,"raw_text":"","unit":"","caliber":"","evidence":""},
 "nature":{"value":null,"raw_text":"","unit":"","caliber":"","evidence":""},
 "text_note":""}

网页正文：
---
%s
---
"""

# ---- 数量解析：从依据里把"30万"算成 300000 ----

_MULT = {"千": 1_000, "万": 10_000, "亿": 100_000_000,
         "k": 1_000, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}

# 单位 → (字段类型, 口径提示)
#
# 英文站占样本 13/94，且数量词是"数字在前"的写法（"79,026 Visitors"）。
# 只收中文单位会让这 14% 的站全部因"依据里没有可解析的数量"被拦——
# 那不是模型答错，是自己认不出，属于批次 1c 踩过的同一个坑。
_UNIT_MAP = {
    "人次": ("visitor", "visit"),
    "平方米": ("area", "gross"), "平米": ("area", "gross"), "㎡": ("area", "gross"),
    "m2": ("area", "gross"), "m²": ("area", "gross"), "平方": ("area", "gross"),
    "面积": ("area", "gross"), "展览面积": ("area", "gross"),
    "展出面积": ("area", "gross"), "展会面积": ("area", "gross"),
    # 中文里名词本身就能当单位："20万+ 行业观众""5000+ 参展企业"。
    # 只认"人/家"会漏掉这一大类写法，而它们在中文首页上比"人"更常见。
    "观众": ("visitor", "person"), "买家": ("visitor", "person"),
    "采购商": ("visitor", "person"), "专业观众": ("visitor", "person"),
    "参展商": ("exhibitor", "company"), "参展企业": ("exhibitor", "company"),
    "展商": ("exhibitor", "company"), "企业": ("exhibitor", "company"),
    "品牌": ("exhibitor", "brand"),
    "展位": ("booth", "booth"),
    "家": ("exhibitor", "company"),
    "人": ("visitor", "person"), "位": ("visitor", "person"), "名": ("visitor", "person"),
    "个": ("booth", "booth"),
    # 英文
    "visitor": ("visitor", "person"), "visitors": ("visitor", "person"),
    "visit": ("visitor", "visit"), "visits": ("visitor", "visit"),
    "buyer": ("visitor", "person"), "buyers": ("visitor", "person"),
    "attendee": ("visitor", "person"), "attendees": ("visitor", "person"),
    "professional": ("visitor", "person"), "professionals": ("visitor", "person"),
    "exhibitor": ("exhibitor", "company"), "exhibitors": ("exhibitor", "company"),
    "company": ("exhibitor", "company"), "companies": ("exhibitor", "company"),
    "brand": ("exhibitor", "brand"), "brands": ("exhibitor", "brand"),
    "supplier": ("exhibitor", "company"), "suppliers": ("exhibitor", "company"),
    "booth": ("booth", "booth"), "booths": ("booth", "booth"),
    "stand": ("booth", "booth"), "stands": ("booth", "booth"),
    "sqm": ("area", "gross"), "sq.m": ("area", "gross"), "sq.m.": ("area", "gross"),
    "sqft": ("area", "gross"), "squaremeters": ("area", "gross"),
    "squaremeter": ("area", "gross"), "squaremetres": ("area", "gross"),
    "squaremetre": ("area", "gross"),
}

# 长的必须排在短的前面：`平方米` 不能被 `平方` 抢先匹配掉，
# `参展企业` 不能被 `企业` 抢先匹配掉，正则交替是"先命中者胜"。
_UNIT_ALT = ("平方米|平米|平方|sq\\.?\\s?m\\.?|sqft|square\\s?met(?:er|re)s?|"
             "㎡|m²|m2|sqm|"
             # "面积" 单独也要收："170,000展览面积(平米)" 去掉括号后是
             # "170,000展览面积平米"，靠"面积"这个尾巴才认得出来。
             "展览面积|展出面积|展会面积|面积|"
             "专业观众|观众|买家|采购商|参展企业|参展商|展商|企业|品牌|展位|"
             "人次|家|人|位|名|个|"
             "visitors|visitor|visits|visit|buyers|buyer|attendees|attendee|"
             "professionals|professional|"
             "exhibitors|exhibitor|companies|company|brands|brand|"
             "suppliers|supplier|booths|booth|stands|stand")

# 数字与单位之间允许的修饰词。真实页面几乎从不写"79,026 Visitors"，
# 而是"79,026 professional visitors"（英文形容词前置）和
# "20万+ 行业观众"（中文把类别词塞在中间）。不允许这段间隔，
# 就等于只认一种写法，剩下全被当成"模型答错"。
# 间隔必须是**非贪婪**的。贪婪量词会先吃掉最长的间隔再回头配单位：
# "5000个展位" 会变成 间隔="个展" + 单位="位"（当成观众数），
# 而不是 间隔="" + 单位="个"。这个 bug 只在有干扰词时出现，很难肉眼发现。
_GAP_CN = r"[\u4e00-\u9fff]{0,5}?"
_GAP_EN = r"(?:[A-Za-z][A-Za-z\-'’]*\s+){0,6}?"

# 末尾的 (?![A-Za-z]) 不能省：没有它，"2500 standard booths" 里的
# standard 会被当成 stand 命中（这里碰巧蒙对），"minutes" 会被当成 "min"。
_QTY = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(千|万|亿|thousand|million|billion|k)?\s*[+＋]?\s*"
    r"(?:" + _GAP_CN + "|" + _GAP_EN + ")"
    r"(" + _UNIT_ALT + r")(?![A-Za-z])",
    re.I)

# ---- 反向语序：标签在前、数字在后 ----
#
# "展商数量5100+专业观众380000+" 这种排版，数字右边紧挨着的名词
# 往往属于**下一个**数量，不是它自己的。只做"数字→单位"的单向匹配，
# 5100 会被当成观众数、380000 反而找不到单位。
# 这里再补一遍"标签→数字"，并且在正向匹配时跳过"单位后面紧跟数字"的情况。
# 这里故意**不收**光秃秃的"面积"：它几乎总是更长标签的尾巴
# （"展会面积800" 里的"面积"前一个字是"会"不是数字，靠数字前缀挡不住），
# 收了就会把"120,000展会面积800"读成"面积 800"。
_LABEL_ALT = ("专业观众|参展企业|展览面积|展出面积|展会面积|观众|买家|采购商|"
              "参展商|展商|企业|品牌|展位")

_LABEL_MAP = {
    "专业观众": ("visitor", "person"), "观众": ("visitor", "person"),
    "买家": ("visitor", "person"), "采购商": ("visitor", "person"),
    "参展商": ("exhibitor", "company"), "参展企业": ("exhibitor", "company"),
    "展商": ("exhibitor", "company"), "企业": ("exhibitor", "company"),
    "品牌": ("exhibitor", "brand"), "展位": ("booth", "booth"),
    "面积": ("area", "gross"), "展出面积": ("area", "gross"),
    "展览面积": ("area", "gross"), "展会面积": ("area", "gross"),
}

# 标签与数字之间不许跨标点，也不许出现另一个数字；开头用 (?<![\d.,])
# 挡住"120,000展会面积800"这类——那里的"展会面积"是前一个数的后缀，
# 不是 800 的前缀。
_QTY_LABEL = re.compile(
    r"(?<![\d.,])(?:" + _LABEL_ALT + r")[^\d。，；、,.;:：()]{0,4}"
    r"(\d[\d,]*(?:\.\d+)?)\s*(千|万|亿)?\s*[+＋]?")
_LABEL_RE = re.compile(r"(?<![\d.,])(" + _LABEL_ALT + r")")


def parse_quantities(text: str) -> list[dict]:
    """从一段原文里解析出所有"数字 + 量级 + 单位"。

    这是核验的核心：模型给 300000，原文写"超30万人次"，
    直接比数字串必然失败，必须先把"30万"折算成 300000 再比。
    """
    # 括号先去掉："170,000展览面积(平米)" 的单位裹在括号里，
    # 不去掉就永远配不上。这里只用于匹配，不影响落库原文。
    flat = re.sub(r"[（()）]", "", _norm_sep(text))
    out: list[dict] = []

    for m in _QTY.finditer(flat):
        # "5100+专业观众380000" 里，"+ "说明 5100 是"5000以上"这种省略写法，
        # 紧跟着的名词其实属于**下一个**数量。只有"带加号 + 单位后面还是数字"
        # 两个条件同时成立才跳过；"120,000展会面积800" 没有加号，是正经的后缀标签，
        # 一刀切会让这类面积直接消失。
        has_plus = "+" in m.group(0) or "＋" in m.group(0)
        if has_plus and flat[m.end():m.end() + 1].isdigit():
            continue
        raw_num = m.group(1).replace(",", "")
        try:
            n = float(raw_num)
        except ValueError:
            continue
        mult = _MULT.get((m.group(2) or "").lower(), 1)
        unit = re.sub(r"\s", "", m.group(3).lower())
        kind, cal = _UNIT_MAP.get(unit, ("unknown", "unknown"))
        ctx = flat[max(0, m.start() - 16): m.end() + 16]
        low = ctx.lower()
        # "个" 是通用量词，单看它什么都推不出来："30 个展馆" 和 "5000 个展位"
        # 长得一模一样。只有左右出现"展位/booth/stand"才敢当展位数，
        # 否则记为 unknown——unknown 永远匹配不上字段类型，等于主动丢弃而非误判。
        if unit == "个":
            if "品牌" in ctx or "brand" in low:
                kind, cal = "exhibitor", "brand"
            elif "展位" in ctx or "booth" in low or "stand" in low:
                kind, cal = "booth", "booth"
            else:
                kind, cal = "unknown", "unknown"
        if kind == "exhibitor":
            if "品牌" in ctx or "brand" in low:
                cal = "brand"
            elif "展位" in ctx or "booth" in low or "stand" in low:
                cal = "booth"
        if "注册" in ctx or "registered" in low:
            cal = "registered"
        # "120000+专业观众(人次)"：口径写在单位后面的括号里。
        # 只看 ±6 字，不能看整个 ctx——同一句里常有
        # "专业观众211,993人，参观人次416,570人次"，看宽了会把"人数"误判成人次。
        if kind == "visitor" and cal != "visit" and "人次" in flat[m.end():m.end() + 6]:
            cal = "visit"
        if kind == "area" and ("净" in ctx or "net" in low):
            cal = "net"
        out.append({"value": n * mult, "unit": re.sub(r"\s", "", m.group(3)),
                    "kind": kind, "caliber": cal, "raw": m.group(0)})

    # 反向语序补一遍
    for m in _QTY_LABEL.finditer(flat):
        label = _LABEL_RE.match(flat[m.start():]).group(1)
        kind, cal = _LABEL_MAP.get(label, ("unknown", "unknown"))
        try:
            n = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        mult = _MULT.get(m.group(2) or "", 1)
        if any(q["kind"] == kind and abs(q["value"] - n * mult) < 1e-6 for q in out):
            continue
        out.append({"value": n * mult, "unit": label, "kind": kind,
                    "caliber": cal, "raw": m.group(0)})

    return out


def _num_ok(value: float, qs: list[dict], want: tuple[str, ...]) -> tuple[bool, str]:
    """数值是否被依据支持：类型要一致，数量级要能对上（容差 3%）。

    want 给一组类型而不是一个：展商数既可能写"2500 家企业"（exhibitor），
    也可能只给"5000 个展位"（booth）。后者不是同一个口径，但确实能算出
    参展规模——放它进来，靠 caliber 字段标明"这是展位数"，而不是直接丢掉。
    """
    cands = [q for q in qs if q["kind"] in want]
    if not cands:
        kinds = sorted({q["kind"] for q in qs})
        if not qs:
            return False, "依据里没有可解析的数量"
        return False, f"依据里的量类型是 {kinds}，不是 {list(want)}"
    for q in cands:
        if abs(q["value"] - value) <= max(abs(value) * 0.03, 1):
            return True, ""
    near = ", ".join("%g" % q["value"] for q in cands[:4])
    return False, f"数值对不上（依据可算出 {near}）"


# ---- 分类字段：值必须在允许集合内，且依据要含该值的判别词 ----
#
# 判别词分强弱，这是这批数据逼出来的结论：真实页面上明确写"仅限专业人士"
# 的很少，多数只写"观众登记""观众注册""30元早鸟票"。
# 前者是硬证据，后者只能算弱证据——只认硬证据会把大半合法数据丢掉，
# 只认弱证据又等于闸门失效。所以两层都收，但**落库时用 conf 区分**，
# 下游要严就只取 medium。
# 两条都不沾的（拿"本人承诺遵守现场秩序"去证明仅限专业观众）仍然拦掉。

ADMISSION_STRONG = {
    # "仅"系词是中文页面表达"不对公众开放"的主要手段，但写法极散：
    # 仅限/仅对/仅供/仅向 专业人士、仅接受预登记…… 只收其中一种必然漏。
    "trade_only": ("仅限", "仅对", "仅供", "仅向", "谢绝", "专业人士", "商业观众",
                   "贸易观众", "采购商", "业内人士", "行业观众", "营业执照", "名片",
                   "审核", "采购商证", "实名", "welcome professionals",
                   "professionals across",
                   "trade only", "trade visitors", "professionals only",
                   "industry professionals", "business visitors", "buyer badge",
                   "not open to the public"),
    "public": ("可购票", "购票", "门票", "售票", "开放给公众", "普通观众", "市民",
               "open to the public", "tickets"),
    "mixed": ("公众开放日", "公众参观日", "专业观众日", "社会观众报名",
              "专业买家及公众", "b2b和b2c", "专业与公众", "批发兼零售",
              "public day", "trade day"),
}
ADMISSION_WEAK = {
    "trade_only": ("登记", "注册", "报名", "预登记", "办证", "仅限", "专业观众", "采购商",
                   "buyer", "trade", "regist", "badge", "visitor category", "professionals"),
    "public": ("观众", "参观", "入园", "票", "大众", "消费者", "public"),
    "mixed": ("前几日", "最后一天", "半程", "融合"),
}
NATURE_STRONG = {
    "B2B": ("专业买家", "采购商", "批发", "贸易", "出口", "订货", "贴牌", "OEM",
            "trade fair", "trade show", "sourcing", "wholesale"),
    "B2C": ("消费者", "零售", "终端消费者", "面向市民", "consumer", "retail"),
    # 两张表的 mixed 必须齐：同一个"公众参观日"既能证明准入混合，
    # 也能证明性质混合，只在一张表里收，另一张就会莫名其妙地漏。
    "mixed": ("b2b和b2c", "专业与公众", "批发兼零售", "公众开放日", "公众参观日",
              "专业买家及公众", "consumer day", "public day"),
}
NATURE_WEAK = {
    "B2B": ("专业", "商贸", "交易", "买家", "展商", "参展", "b2b", "trade", "buyer"),
    "B2C": ("消费", "市民", "大众", "公众", "b2c", "consumer"),
    "mixed": ("兼", "融合", "b2c"),
}


# mixed 不能靠列举短语来认。它本质是"专业侧和公众侧同时出现"，
# 所以改成结构化判定：两侧各有一套词，两边都命中才算 mixed。
# 实测依据"专业观众预约登记 消费者参观购票"——一眼就是 mixed，
# 但任何一个具体短语都不在列表里，靠枚举永远补不全。
ADM_TRADE_VOCAB = ("专业观众", "采购商", "名片", "营业执照", "仅限", "仅对", "谢绝",
                   "人士", "登记", "注册", "办证", "胸卡", "badge", "trade", "buyer",
                   "professional", "regist")
ADM_PUBLIC_VOCAB = ("公众", "普通观众", "市民", "大众", "消费者", "购票", "门票",
                    "售票", "票", "public", "ticket", "consumer")
NAT_B2B_VOCAB = ("专业", "买家", "采购", "批发", "贸易", "出口", "订货", "经销",
                 "从业者", "展商", "sourcing", "wholesale", "trade", "buyer", "b2b")
NAT_B2C_VOCAB = ("消费者", "零售", "终端", "市民", "大众", "公众", "消费",
                 "consumer", "retail", "b2c")


def _cat_ok(value: str, ev_flat: str, table: tuple[dict, dict],
            ctx: str | None = None) -> tuple[bool, str, str]:
    """返回 (是否保留, 置信度, 原因)。置信度 medium=硬证据，low=只有弱证据。

    ctx 是依据在正文里的**邻近上下文**，只给 mixed 用：
    mixed 的定义是"两侧同时出现"，而模型抄依据时经常只抄一侧
    （正文写"专业观众预约登记，消费者参观购票"，它只抄前半句）。
    只在紧邻的句子里找另一侧，锚点仍是真实正文，不是无中生有。
    """
    strong, weak = table
    if value not in strong:
        return False, "", f"取值 {value} 不在允许集合 {sorted(strong)}"
    low = ev_flat.lower()

    if value == "mixed":
        trade, public = (ADM_TRADE_VOCAB, ADM_PUBLIC_VOCAB) if weak is ADMISSION_WEAK \
            else (NAT_B2B_VOCAB, NAT_B2C_VOCAB)
        wide = (ctx or ev_flat).lower()
        a = any(k in wide for k in trade)
        b = any(k in wide for k in public)
        if a and b:
            return True, "medium", ""
        if any(k in low for k in strong[value]):
            return True, "low", ""
        return False, "", "依据里只出现了一侧（专业/公众），不足以判 mixed"

    if any(k in low for k in strong[value]):
        return True, "medium", ""
    if any(k in low for k in weak[value]):
        return True, "low", ""
    return False, "", f"依据里没有支持 {value} 的判别词（连弱证据都没有）"


_LOCK = threading.Lock()


def shape(rid: str, body: str, raw: str) -> dict:
    """解析 + 核验。不联网，可离线重跑。"""
    data = _json_of(raw)
    body_flat = _flat(_norm_sep(body))
    out = {"id": rid, "fields": {}, "dropped": {}, "ok": False, "raw": raw[:1400]}
    if not data:
        out["error"] = "LLM 未返回可解析 JSON"
        return out

    note = (data.get("text_note") or "").strip()
    if note:
        out["text_note"] = note[:200]

    for k in FIELDS:
        cell = data.get(k)
        if not isinstance(cell, dict):
            continue
        v, ev, rtext = cell.get("value"), cell.get("evidence", ""), cell.get("raw_text", "")
        ev_n = _norm_sep(str(ev or "")).strip()
        ev_flat = _flat(ev_n)
        if len(ev_flat) < 4:
            continue

        # 模型明确表示"页面上没有"（value=null）的字段，是**没抽到**，不是**被拦下**。
        # 混进 dropped 会让拦截率虚高，看起来像闸门在误杀。
        if v is None or (isinstance(v, str) and not v.strip()):
            continue

        if ev_flat not in body_flat:
            out["dropped"][k] = {"value": v, "why": "依据不在正文中", "evidence": ev_flat[:40]}
            continue

        if k in ("admission", "nature"):
            table = (ADMISSION_STRONG, ADMISSION_WEAK) if k == "admission" \
                else (NATURE_STRONG, NATURE_WEAK)
            idx = body_flat.find(ev_flat)
            ctx = body_flat[max(0, idx - 60): idx + len(ev_flat) + 160] if idx >= 0 else None
            ok, conf, why = _cat_ok(str(v or ""), ev_flat, table, ctx)
            if not ok:
                out["dropped"][k] = {"value": v, "why": why, "evidence": ev_flat[:40]}
                continue
            out["fields"][k] = {"value": v, "method": "llm",
                                "evidence": ev_flat[:80], "conf": conf}
            continue

        # 数值字段
        try:
            num = float(v)
        except (TypeError, ValueError):
            out["dropped"][k] = {"value": v, "why": "取值不是数字"}
            continue
        if num <= 0:
            out["dropped"][k] = {"value": v, "why": "取值非正数"}
            continue

        if "area" in k:
            want = ("area",)
        elif "exhibitor" in k:
            want = ("exhibitor", "booth")   # 只给展位数也认，靠 caliber 标明
        else:
            want = ("visitor",)

        qs = parse_quantities(ev_n)
        ok, why = _num_ok(num, qs, want)
        span = "evidence"

        # 依据段里凑不出数，但 raw_text 自己能在正文里找到——用 raw_text 再算一次。
        # 模型常把依据抄成一句概括语（"本届规模创新高"），而把真正含数字的
        # 短语放在 raw_text 里。只要 raw_text 逐字出现在正文，锚点就是真的，
        # 换一个更小的锚点重算，比直接丢掉合理。
        if not ok:
            rt_n = _norm_sep(str(rtext or "")).strip()
            if len(_flat(rt_n)) >= 3 and _flat(rt_n) in body_flat:
                qs2 = parse_quantities(rt_n)
                ok2, why2 = _num_ok(num, qs2, want)
                if ok2:
                    ok, why, qs, span = True, "", qs2, "raw_text"
                else:
                    why = f"{why}；仅用 raw_text 也{why2}"
        if not ok:
            out["dropped"][k] = {"value": v, "why": why, "evidence": ev_flat[:40]}
            continue

        # 口径：模型的自述优先，但必须与依据算出来的一致，否则以依据为准
        cal = (cell.get("caliber") or "").strip().lower()
        matched = min((q for q in qs if q["kind"] in want),
                      key=lambda q: abs(q["value"] - num))
        if not cal:
            cal = matched["caliber"]
        elif cal != matched["caliber"] and matched["caliber"] != "unknown":
            out.setdefault("caliber_conflict", {})[k] = {
                "model": cal, "from_text": matched["caliber"], "use": matched["caliber"]}

        out["fields"][k] = {
            "value": int(round(num)),
            "method": "llm",
            "raw_text": str(rtext or matched["raw"])[:40],
            "unit": matched["unit"],
            "caliber": matched["caliber"] if matched["caliber"] != "unknown" else cal,
            "evidence": ev_flat[:80],
            "evidence_span": span,
            "conf": "medium",
        }

    # 模型在 text_note 里自述"口径存疑 / 不是本页主体"时，它其实知道这个数有问题，
    # 却还是会填进去（实测 SIAL 把广州子展的 66,517 填成了上海展的上届观众）。
    # 闸门管不了语义，但至少要把这类记录标出来，别混在正常数据里。
    if note and any(w in note for w in ("存疑", "不确定", "无法确定", "疑似",
                                        "非本", "其他展", "子展", "并非本")):
        out["review"] = True
        for cell in out["fields"].values():
            cell["conf"] = "low"

    out["ok"] = bool(out["fields"])
    out["filled"] = len(out["fields"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reverify", action="store_true")
    args = ap.parse_args()

    BATCH2.mkdir(parents=True, exist_ok=True)
    ids = all_ids()
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        ids = [i for i in ids if i in want]
    if args.limit:
        ids = ids[: args.limit]

    if args.reverify:
        if not OUT.exists():
            print("✗ 没有 %s，无从重跑" % OUT, file=sys.stderr)
            return 2
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        recs, net = [], 0
        for r in prev.get("records", []):
            if not r.get("raw"):
                recs.append(r)
                continue
            # 正文一律走 load_body：它会自动把补充子页拼上。
            # 旧记录里的 body_src 是 "raw"/"rendered"，现在还有 "main"/"sub"，
            # 按目录名去拼路径会在换版本后指向不存在的文件。
            body = load_body(r["id"])
            if not body:
                recs.append(r)
                continue
            src = "sub" if (SUB_DIR / f"{r['id']}.txt").exists() else "main"
            before = len(r.get("fields", {}))
            fixed = shape(r["id"], body, r["raw"])
            fixed["body_src"] = src
            fixed["model"] = r.get("model")
            recs.append(fixed)
            net += len(fixed["fields"]) - before
            print("  %-20s %d → %d" % (r["id"], before, len(fixed["fields"])))
        prev["records"] = recs
        prev["reverified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        OUT.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n重核验完成：净变化 %+d 个字段｜模型未被调用" % net)
        return 0

    done: dict[str, dict] = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            sel = set(ids)
            if args.force:
                # --force 只对**本次选中的**展会重抽。选择之外的记录必须原样保留：
                # 否则一次 "──only 6 个站 --force" 就会把其余 70 多个展的结果清空
                # （这一版实测踩过，白跑了 81 个站）。
                done = {r["id"]: r for r in prev.get("records", []) if r["id"] not in sel}
            else:
                done = {r["id"]: r for r in prev.get("records", []) if r.get("ok")}
        except (json.JSONDecodeError, KeyError):
            done = {}
    bodies = {i: load_body(i) for i in ids}
    todo = [i for i in ids if i not in done and bodies[i] is not None]

    provider = _build_real_provider()
    if provider is None:
        print("✗ 没有可用的 LLM key。见 expohub-backend/.env", file=sys.stderr)
        return 2

    print("待抽 %d 个（已完成 %d）｜模型 %s" % (len(todo), len(done), provider._model))
    if args.dry_run:
        return 0

    results = list(done.values())
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(_one, provider, i): i for i in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            rid = futs[fut]
            try:
                r = fut.result()
            except Exception as ex:
                r = {"id": rid, "ok": False, "fields": {}, "dropped": {},
                     "error": f"{type(ex).__name__}: {str(ex)[:60]}"}
            src = "sub" if (SUB_DIR / f"{rid}.txt").exists() else "main"
            r["body_src"] = src
            with _LOCK:
                results.append(r)
                OUT.write_text(json.dumps(
                    {"model": provider._model,
                     "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     "records": results}, ensure_ascii=False, indent=2), encoding="utf-8")
            print("  [%3d/%3d] %d/8 %-20s %s" % (n, len(todo), r.get("filled", 0), rid,
                                                 r.get("error", "")))

    ok = [r for r in results if r.get("ok")]
    fill = {k: sum(1 for r in ok if k in r["fields"]) for k in FIELDS}
    print("\n完成 %d ｜ 有字段 %d ｜ 拦下 %d ｜ 用时 %.0f 秒" % (
        len(ok), sum(r.get("filled", 0) for r in ok),
        sum(len(r.get("dropped", {})) for r in results), time.time() - t0))
    print("\n字段填充率（分母 = %d 个有结果的展）" % len(ok))
    for k in FIELDS:
        print("  %-20s %3d  %4.0f%%" % (k, fill[k], 100 * fill[k] / max(len(ok), 1)))
    print("\n→ %s" % OUT)
    return 0


def _one(provider: OpenAICompatProvider, rid: str) -> dict:
    body = load_body(rid) or ""
    raw = provider.complete_full(PROMPT % _slices(body, kws=SCALE_KWS, tail=12000),
                                 system=SYSTEM, temperature=0.0, max_tokens=700)
    r = shape(rid, body, raw)
    r["model"] = provider._model
    return r


if __name__ == "__main__":
    sys.exit(main())
