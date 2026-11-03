"""
E1 / E4 纯函数（无 IO、无数据库依赖，可单测）

这些函数是画像层唯一"算"的部分。刻意不做加权和：
- E1 输出区间而非点值（三个估计量相乘，误差会复合）
- E4 是纯时间函数，不加权

对应文档：docs/展会画像-维度清单.md 第 10.2 / 10.5 节
"""

from __future__ import annotations

from datetime import date
from typing import Optional

# ---- 观众/展商比档位（维度清单 10.2，v2 重标定）----
#
# v1 的档位是拍的：≥25 充裕 / 10~25 正常 / 8~10 偏薄 / <8 摊薄严重。
# 批次 2 拿 27 个真实可算比值的展一验，**没有一个低于 13**——那条 <8 的
# 硬门限在真实数据上一次都触发不了，等于没写。
#
# v2 改成按本样本四分位切。v3 是因为补采之后样本从 27 涨到 35，
# 分位跟着移动了 20 分——**这正是相对档位的代价，也是它诚实的地方**：
# 常量必须跟着样本走，否则"前 25%"这个说法就名不副实。
#   归一化后（人次÷2）P25=25.4 / P50=40.0 / P75=73.3，n=35
#   原始未归一        P25=33.7 / P50=62.5 / P75=75.0
# v2 的 24.5/60.0/75.0 对应 n=27，已作废（保留在 persona_param 的历史里）。
#
# 为什么敢用分位而不是绝对阈值：这几个数都是主办方的宣传口径，绝对值
# 不可比（谁都想把分子写大），但"在同期样本里排第几"是可比的。
# 代价是它是**相对档位**，换样本要重算——所以版本号写进常量名。
#
# 绝对下限单独留着：不管分位怎么切，每个展位分不到 5 个观众就是摊薄，
# 这是口径无关的常识判断。当前样本里不触发，但能挡住未来混进来的脏数据。
RATIO_BANDS: list[tuple[float, str]] = [
    (73.3, "ample"),      # ≥P75   客源相对充裕（样本前 25%）
    (40.0, "normal"),     # ≥P50   正常
    (25.4, "thin"),       # ≥P25   偏薄
    (0.0, "severe"),      # <P25   摊薄（样本后 25%）
]
RATIO_ABS_FLOOR = 5.0     # 绝对下限：低于此值无条件 severe
RATIO_CALIBRATION = {
    "version": "v3-2026-11-03",
    "basis": "persona.db 35 个可算比值的展（补采后），人次已÷2 归一",
    "p25": 25.4, "p50": 40.0, "p75": 73.3, "n": 35,
    "raw_p25": 33.7, "raw_p50": 62.5, "raw_p75": 75.0,
    "superseded": "v2-2026-11-03 (n=27, 24.5/60.0/75.0)",
    "note": "相对档位，换样本需用 compute_persona.py --calibrate 重算",
}

# 人次 ÷ 人数 的折算系数。维度清单给的是 1.8~2.5 倍，取中点 2.0。
# 这个系数直接决定 9 个"报人次"的展的比值（÷2 后 sh-gift 从 26.7 掉到 13.3），
# 所以它是个必须写进参数表的旋钮，不能散落在代码里。
VISIT_TO_PERSON = 2.0

# ---- 展位窗口档位（维度清单 10.5）----
# 距截止 >120 天 充裕 ｜ 60~120 正常 ｜ 0~60 紧张 ｜ 已过 关闭
DEADLINE_BANDS: list[tuple[float, str]] = [
    (120.0, "ample"),
    (60.0, "normal"),
    (0.0, "urgent"),
]

# ---- E4 备用档位：按「距开展天数」分档 ----
# 为什么要有这一组：批次 1 实测 80 个可用站里，报名截止日填充率是 **0%**
# （63 个页面一处都没写）。原先 E4 的主因子"截止日倒计时"在真实数据上不存在，
# 只能退回唯一还站得住的时间锚——开展日。
#
# 档位名刻意不用 closed/urgent 这类容易被误读成"去不了"的词：
# 距开展 5 天不等于"关门"，只等于"好位置大概率没了"。前者是门限，后者是提示。
START_WINDOW_BANDS: list[tuple[float, str]] = [
    (180.0, "ample"),      # >180 天  早鸟期，位置最全
    (90.0, "normal"),      # 90~180   正常招展期
    (45.0, "tight"),       # 45~90    偏紧
    (15.0, "urgent"),      # 15~45    紧，该现在就联系主办方
    (4.0, "critical"),     # 4~14     很紧，基本只剩边缘位
    (0.0, "impossible"),   # 0~3      基本不可能，除非主办方现场售位
]

# 真正能"一票否决"的只有下面这条边界，其余全部降为提示。
# 依据：售罄/余量数据覆盖率为 0，E4 没有任何证据说"已经没位了"，
# 它只有资格说"来不及了"。把 44% 覆盖的粗粒度信号当门限，
# 会造成大面积假否决——而假否决的代价是用户永久失去一个机会，
# 比漏判更不可逆。
HARD_STOP_DAYS = 3

# ---- E2 竞争密度：v1 暂停使用 ----
#
# 原公式 1/(1+max(0,竞品数-3)×0.12) 的前提是"竞品数在个位数到几十"。
# 批次 3 实测：CMEF 名录 13,306 家、同品类 10,449 家 → 因子 0.0008；
# 高交会 929 → 0.0089。竞品数一过 11，因子就跌破 0.51，实际上是个常数 0。
# 把它乘到 E1 上，等于把这两个展的客群估计直接归零——比不乘更糟。
#
# 更根本的问题是数据不够：94 个展里只有 2 个既能拿到名录、又有品类标注。
# 在没有数据的地方标定参数，标出来的只是自己的假设。
E2_STATUS = {
    "enabled": False,
    "version": "paused-2026-11-03",
    "reason": "名录可得率 3.2%（94 展仅 3 个有可计条数，2 个有品类标注），"
              "且原公式在真实名录规模下饱和（竞品 10449 → 因子 0.0008），"
              "会把 E1 乘成 0。待名录+品类数据到位后按「竞品占比」重标定。",
    "calibrated_n": 2,
}

# ---- E1 角色命中率的三个档位（唯一需要人工标定的参数之一）----
ROLE_HIT_LOW = 0.05
ROLE_HIT_MID = 0.20
ROLE_HIT_HIGH = 0.45


def normalize_visitor_count(value: Optional[float], caliber: Optional[str]) -> Optional[int]:
    """
    把观众数折算成"人数"。

    人次 ÷ VISIT_TO_PERSON 是维度清单里定的兜底规则：3 天展期每天重复进场，
    人次≈人数的 1.8~2.5 倍。**绝不把人次直接当人数用**，否则 E1 高估 2~3 倍。
    口径未知时按 unknown 处理——返回 None 而不是猜，让调用方标低置信度。
    """
    if value is None or value <= 0:
        return None
    c = (caliber or "unknown").lower()
    if c == "person":
        return int(round(value))
    if c == "visit":  # 人次
        return int(round(value / VISIT_TO_PERSON))
    # registered / unknown 一律不硬转，交由人工确认
    return None


def visitor_exhibitor_ratio(
    visitor_count: Optional[int], exhibitor_count: Optional[int]
) -> tuple[Optional[float], str]:
    """
    观众/展商比 = 专业观众数 ÷ 展商数

    这是 E1 里唯一"公开数据当天就能算"的硬指标。
    返回 (ratio, band)；任一缺失返回 (None, "unknown")。
    """
    if not visitor_count or not exhibitor_count or exhibitor_count <= 0:
        return None, "unknown"
    ratio = round(visitor_count / exhibitor_count, 2)
    if ratio < RATIO_ABS_FLOOR:
        return ratio, "severe"      # 绝对下限优先于分位档位
    return ratio, _band_of(ratio, RATIO_BANDS)


def e2_discount(competitor_count: Optional[int],
                exhibitor_count: Optional[int] = None) -> tuple[Optional[float], str]:
    """
    E2 竞争密度折扣。v1 处于暂停状态，这里恒返回 (None, 原因)。

    保留函数签名是给下游一个稳定的接口：调用方拿到 None 就知道"这一项
    现在是关的"，而不是拿到一个 0.0008 然后默默把 E1 乘没。
    """
    if not E2_STATUS["enabled"]:
        return None, E2_STATUS["reason"]
    if not competitor_count or not exhibitor_count:
        return None, "缺竞品数或展商总数"
    # 占位实现：按占比算，指数待标定（原绝对数公式已证明会饱和）
    share = competitor_count / max(exhibitor_count, 1)
    return round(1 / (1 + max(0.0, share - 0.05) * 2.0), 3), ""


def _band_of(value: float, bands: list[tuple[float, str]]) -> str:
    for threshold, name in bands:
        if value >= threshold:
            return name
    return bands[-1][1]


def e1_target_range(
    visitor_count: Optional[int],
    rank_discount: float = 1.0,
    low: float = ROLE_HIT_LOW,
    mid: float = ROLE_HIT_MID,
    high: float = ROLE_HIT_HIGH,
) -> dict:
    """
    E1 目标角色到场人数区间。

        lo  = 观众数 × 角色命中率(低档) × 职级折扣
        mid = 观众数 × 角色命中率(中档) × 职级折扣
        hi  = 观众数 × 角色命中率(高档) × 职级折扣

    rank_discount = 决策层 + 0.3×建议层 + 0.1×执行层（由观众职级构成算出，
    拿不到职级构成时取 1.0，不假装精确）。
    """
    if not visitor_count or visitor_count <= 0:
        return {"lo": None, "mid": None, "hi": None, "confidence": "low"}
    return {
        "lo": int(round(visitor_count * low * rank_discount)),
        "mid": int(round(visitor_count * mid * rank_discount)),
        "hi": int(round(visitor_count * high * rank_discount)),
        # 命中率是标定值而非实测值时，置信度最高只能到 mid
        "confidence": "mid" if rank_discount != 1.0 else "low",
    }


def booth_window(
    deadline_iso: Optional[str],
    today: Optional[date] = None,
    last_soldout_days_before: Optional[int] = None,
) -> dict:
    """
    E4 展位可得性：纯时间函数。

    如果拿到"上届售罄日距开展 X 天"，且当前剩余天数已小于 X，
    说明按去年节奏此时应已售罄，直接给 likely_full —— 这比档位更有说服力。
    """
    today = today or date.today()
    if not deadline_iso:
        return {"days_left": None, "band": "unknown", "deadline": None, "note": "无截止日"}

    try:
        deadline = date.fromisoformat(deadline_iso[:10])
    except ValueError:
        return {"days_left": None, "band": "unknown", "deadline": deadline_iso,
                "note": "截止日格式非法"}

    days_left = (deadline - today).days

    if days_left < 0:
        band = "closed"
    else:
        band = _band_of(float(days_left), DEADLINE_BANDS)

    note = ""
    if last_soldout_days_before is not None and days_left >= 0:
        if days_left < last_soldout_days_before:
            band = "likely_full"
            note = f"上届开展前 {last_soldout_days_before} 天售罄，当前仅剩 {days_left} 天"

    return {"days_left": days_left, "band": band, "deadline": deadline_iso, "note": note}


def booth_window_by_start(start_iso: Optional[str], today: Optional[date] = None) -> dict:
    """
    E4 单因子版：只按「距开展天数」分档，不依赖截止日。

    这是真实数据逼出来的降级，不是设计偏好。截止日在 80 个可采站点里
    一处都抽不到（主办方普遍不公开、或写成"额满即止"），继续把 E4
    挂在截止日上等于整项失效。而开展日有 52.5% 填充率，够用。

    role 字段是这次调整的核心：
      gate     —— **只有"来不及"才算门限**：本届已结束，或距开展 ≤ HARD_STOP_DAYS
      advisory —— 其余全部是提示，不得否决
    往届日期算出来的 days_left 是负数，如果直接进档位会得到 closed，
    等于用"去年已经办完了"去否决"今年还去不去"——这是最坏的一类假否决。
    """
    today = today or date.today()
    if not start_iso:
        return {"days_left": None, "band": "unknown", "role": "advisory",
                "start_date": None, "note": "无开展日"}

    try:
        start = date.fromisoformat(start_iso[:10])
    except ValueError:
        return {"days_left": None, "band": "unknown", "role": "advisory",
                "start_date": start_iso, "note": "开展日格式非法"}

    days_left = (start - today).days

    # 已过 90 天 → 这是往届日期，只作季节参考，不参与可得性判断
    if days_left < -90:
        return {"days_left": None, "band": "unknown", "role": "advisory",
                "start_date": start_iso,
                "note": f"开展日已过去 {-days_left} 天，属往届，仅供参考"}
    # 已开展但未满 90 天：展已经办完了，不能当"紧张"，只能当 closed
    if days_left < 0:
        return {"days_left": days_left, "band": "closed", "role": "gate",
                "start_date": start_iso, "note": "已开展，本届无法再订展位"}

    band = _band_of(float(days_left), START_WINDOW_BANDS)
    role = "gate" if days_left <= HARD_STOP_DAYS else "advisory"
    return {"days_left": days_left, "band": band, "role": role,
            "start_date": start_iso, "note": ""}


def season_prior(past_start_iso: Optional[str], today: Optional[date] = None) -> dict:
    """
    往届日期的正确用法：不当日期用，当「季节性先验」用。

    拿到一个已结束的往届展期，能可靠导出的只有一件事——这个展通常几月办。
    年份推不出来（年展/双年展/停办一轮都长得一样），所以只给月份，
    并明确标 estimated=True。用途是 B5 行程节奏、B6 撞期判断、
    以及详情页那句"该展通常在 11 月举办"，**不进 E4 的档位计算**。
    """
    today = today or date.today()
    if not past_start_iso:
        return {"typical_month": None, "season_label": None, "estimated": True, "stale": True}
    try:
        start = date.fromisoformat(past_start_iso[:10])
    except ValueError:
        return {"typical_month": None, "season_label": None, "estimated": True, "stale": True}

    months_ago = (today.year - start.year) * 12 + (today.month - start.month)
    # 超过 24 个月说明可能已换届期或停办，季节信号也开始不可信
    return {
        "typical_month": start.month,
        "season_label": f"{start.month} 月",
        "months_ago": months_ago,
        "estimated": True,
        "stale": months_ago > 24,
    }


def compute_all(
    visitor_count: Optional[int],
    exhibitor_count: Optional[int],
    visitor_caliber: Optional[str] = None,
    deadline_iso: Optional[str] = None,
    today: Optional[date] = None,
    last_soldout_days_before: Optional[int] = None,
    start_date_iso: Optional[str] = None,
    dates_status: Optional[str] = None,
) -> dict:
    """
    一次算完 E1 + E4，写入 ExpoPersona 用。

    E4 取值优先级（这是"往期兜底"后的口径）：
      1. 有截止日 → booth_window（原设计，最准）
      2. 无截止日、有本届开展日 → booth_window_by_start（实测唯一可行的路）
      3. 开展日属往届 → 只出季节先验，e4_band=unknown、e4_role=advisory
    dates_status 由采集层给出：current / past / none。
    """
    v = normalize_visitor_count(visitor_count, visitor_caliber)
    ratio, ratio_band = visitor_exhibitor_ratio(v, exhibitor_count)
    e1 = e1_target_range(v)

    # 比值是不是靠折算得来的，必须让下游知道：报人次的站，比值是
    # "原始数 ÷ 2"，而这个 2 是假设不是实测。同样的比值，可信度不同。
    basis = "unknown"
    if ratio is not None:
        basis = "converted_from_visit" if (visitor_caliber or "").lower() == "visit" else "person"
    e2, e2_note = e2_discount(None)

    if deadline_iso:
        e4 = booth_window(deadline_iso, today, last_soldout_days_before)
        e4["role"] = "gate"
        e4.setdefault("source", "deadline")
    elif start_date_iso and dates_status != "past":
        e4 = booth_window_by_start(start_date_iso, today)
        e4["source"] = "start_date"
    else:
        e4 = {"days_left": None, "band": "unknown", "role": "advisory",
              "deadline": None, "start_date": start_date_iso,
              "note": "无本届可用日期", "source": "none"}

    season = season_prior(start_date_iso if dates_status == "past" else None, today)

    return {
        "visitor_count_normalized": v,
        "visitor_exhibitor_ratio": ratio,
        "ratio_band": ratio_band,
        "ratio_basis": basis,
        "e2_discount": e2, "e2_note": e2_note,
        "e1_lo": e1["lo"], "e1_mid": e1["mid"], "e1_hi": e1["hi"],
        "e1_confidence": e1["confidence"],
        "e4_band": e4["band"], "e4_days_left": e4["days_left"],
        "e4_deadline": e4.get("deadline"),
        "e4_role": e4["role"], "e4_source": e4.get("source"),
        "e4_note": e4["note"],
        "season_typical_month": season["typical_month"],
        "season_label": season.get("season_label"),
        "season_stale": season["stale"],
    }


def self_check() -> list[str]:
    """内置自检，返回失败项（空列表 = 全通过）"""
    fails = []

    # 人次折算
    if normalize_visitor_count(300000, "visit") != 150000:
        fails.append("人次折算未按 ÷2")
    if normalize_visitor_count(300000, "person") != 300000:
        fails.append("人数不应折算")
    if normalize_visitor_count(300000, "unknown") is not None:
        fails.append("口径未知不应硬转")

    # 档位边界（v3 四分位 + 绝对下限）
    cases = [(200, "ample"), (73.3, "ample"), (73.2, "normal"), (40, "normal"),
             (39.9, "thin"), (25.4, "thin"), (25.3, "severe"), (13.3, "severe")]
    for ratio, expect in cases:
        got = _band_of(ratio, RATIO_BANDS)
        if got != expect:
            fails.append(f"ratio {ratio} 应为 {expect}，实为 {got}")
    if visitor_exhibitor_ratio(5000, 1000)[1] != "severe":
        fails.append(f"比值 5 应被绝对下限判 severe，实为 {visitor_exhibitor_ratio(5000, 1000)}")

    # 人次折算的系数必须来自常量，不能写死
    if normalize_visitor_count(300000, "visit") != int(round(300000 / VISIT_TO_PERSON)):
        fails.append("人次折算未使用 VISIT_TO_PERSON")

    # E2 暂停时必须显式返回 None + 原因，不能返回一个乘数
    d2, why2 = e2_discount(10449, 13306)
    if d2 is not None or not why2:
        fails.append("E2 暂停期间必须返回 (None, 原因)")

    # E4
    d = date(2026, 11, 3)
    r = booth_window("2026-11-02", d)
    if r["band"] != "closed":
        fails.append("已过截止应为 closed")
    r = booth_window("2027-06-01", d)
    if r["band"] != "ample":
        fails.append(">120 天应为 ample")
    r = booth_window("2027-06-01", d, last_soldout_days_before=300)
    if r["band"] != "likely_full":
        fails.append("已过去年售罄点应为 likely_full")
    r = booth_window("额满即止", d)
    if r["band"] != "unknown":
        fails.append("非 ISO 截止日应为 unknown")

    # ---- E4 单因子版（距开展天数）----
    r = booth_window_by_start("2027-06-01", d)          # 210 天后
    if r["band"] != "ample" or r["role"] != "advisory":
        fails.append(f"210 天应为 ample/advisory，实为 {r['band']}/{r['role']}")
    r = booth_window_by_start("2027-01-15", d)          # 73 天后
    if r["band"] != "tight" or r["role"] != "advisory":
        fails.append(f"73 天应为 tight/advisory，实为 {r['band']}/{r['role']}")
    r = booth_window_by_start("2026-11-20", d)          # 17 天后
    if r["band"] != "urgent" or r["role"] != "advisory":
        fails.append(f"17 天应为 urgent/advisory，实为 {r['band']}/{r['role']}")
    r = booth_window_by_start("2026-11-08", d)          # 5 天后：很紧，但仍不是门限
    if r["band"] != "critical" or r["role"] != "advisory":
        fails.append(f"5 天应为 critical/advisory（不得否决），实为 {r['band']}/{r['role']}")
    r = booth_window_by_start("2026-11-05", d)          # 2 天后：确实来不及了
    if r["band"] != "impossible" or r["role"] != "gate":
        fails.append(f"2 天应为 impossible/gate，实为 {r['band']}/{r['role']}")
    # 关键：往届日期绝不能算出 closed 去否决本届
    r = booth_window_by_start("2025-04-21", d)
    if r["band"] != "unknown" or r["role"] != "advisory":
        fails.append(f"往届日期应为 unknown/advisory（不得否决），实为 {r['band']}/{r['role']}")
    if r["days_left"] is not None:
        fails.append("往届日期不应给出 days_left")

    # ---- 季节先验 ----
    s = season_prior("2025-04-21", d)                   # 19 个月前，仍在 24 个月容忍期内
    if s["typical_month"] != 4 or s["stale"] is not False:
        fails.append(f"2025-04 距今 19 个月应取 month=4 且不 stale，实为 {s}")
    s = season_prior("2023-04-21", d)
    if s["stale"] is not True:
        fails.append("超过 24 个月应标 stale")
    if season_prior(None, d)["typical_month"] is not None:
        fails.append("无往届日期不应给月份")

    # ---- compute_all 的 E4 优先级 ----
    a = compute_all(None, None, deadline_iso="2027-06-01", today=d)
    if a["e4_source"] != "deadline" or a["e4_role"] != "gate":
        fails.append("有截止日应优先用截止日并当门限")
    b = compute_all(None, None, start_date_iso="2027-01-15", today=d, dates_status="current")
    if b["e4_source"] != "start_date" or b["e4_band"] != "tight":
        fails.append("无截止日应退回开展日")
    c = compute_all(None, None, start_date_iso="2025-04-21", today=d, dates_status="past")
    if c["e4_band"] != "unknown" or c["season_typical_month"] != 4:
        fails.append("往届应只出季节先验")

    return fails
