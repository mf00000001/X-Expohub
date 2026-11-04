"""
规模三件套的多路估算（estimate）

## 这个模块要解决的问题

94 个展里，观众数只有 49 个、展商数 47 个、面积 39 个、展位价 0 个。
列表翻到第二页就是一片空白，**空白的页面对着干瘪的数据**——用户没法判断
"这个展值不值得去"，演示也就没法看。

但补数据有两条路，只有一条是对的：

1. 去网上再爬一遍。已经爬了四轮，2670 条索引全覆盖，剩下的确实是主办方
   没公开（尤其是展位价和地方小展的规模数）。这条路走到底了。
2. **用已有数据估。** 前提是估算必须能被复核，且**永远不许冒充实测**。

本模块做第 2 条。

## 为什么基准取"数据自身的分布"，不取行业口诀

行业里通行"9㎡ 一个标准展位"，听起来权威。但拿它算这个展有多少展商，
会系统性高出 3~8 倍——因为实际每个展商平均占用远大于 9㎡（特装搭建、
通道、公共区域、主办方自用面积都要摊进去）。

35 个三件套齐全的实测展算出来的真实密度是 **12.5 家/千㎡**（p25=8.8, p75=19.5），
换算下来平均每个展商占 80㎡。这个数字难看，但它是这批数据自己的规律，
而且能说清"我从哪 35 个数算出来的"。

**用外部经验当基准，错了没人能查；用样本分布当基准，错了能倒查是哪几个样本带偏的。**

## 为什么必须多路证据

单路估算的错误无法被自己发现。

典型例子：东莞名家具展记录的展览面积是 100 万㎡，实际广东现代国际展览中心
室内只有约 13 万㎡——那个数显然是把园区总建筑面积填进来了。如果只用"面积 × 密度"
这一路，会得出 12500 家展商，荒谬但没人拦得住。

但如果同时跑"同城同品类类比"这一路，它会给出 2000 家左右。两路差 6 倍，
系统自己就知道这个估算不能信（见 `_fuse` 的 4.0 倍否决线）。

所以每一路证据都独立算一个值，最后看它们收敛不收敛。**这是"多验证"的全部含义**：
不是把同一个公式算三遍，是用三种互相独立的推算路径去撞同一个数。

## 三条铁律

1. **估算值绝不覆盖实测值。** 已有数一律不动，哪怕看起来可疑。可疑值走
   `data_status='pending_verify'` 交人工，不用估算悄悄替换掉——
   一旦开了这个口，就再也分不清库里哪个数是人给的、哪个是算出来的。
2. **估算值绝不能当证据再去估别的。** 证据只从 measured 集合取。否则
   A 的误差会进 B，B 的误差再进 C，三级之后没人知道偏离了多少。
   代价是覆盖率上不去（大概多补 30 个点），这个代价必须付。
3. **估不出来就是估不出来。** 三路差 4 倍以上、或者一路证据都没有，
   返回 None，字段保持空白。宁可页面上显示"未公开"，也不要显示一个
   看起来精确的假数——假数会被拿去做决策。

## 与 bands.py 的关系

这里不碰档位，只补数。补完之后比值仍然走 `visitor_exhibitor_ratio()`，
档位仍然是相对排名。估算出来的比值天然会往中位数收（因为基准就是中位数），
所以**估算条目的档位要标低置信度**，不能和实测条目平起平坐——
这一点由 `compute_persona.py` 消费 `confidence` 时体现。

对应文档：docs/展会画像-维度清单.md 第 10.2 节
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Iterable, Optional

from app.models.category import CATEGORY_PARENT_GROUPS
from app.modules.persona.bands import normalize_visitor_count

# ============================================================
# 常量与阈值
# ============================================================

# 单馆展览面积上限。中国最大的单体展馆（深圳国际会展中心一期）室内约 40 万㎡，
# 留 25% 余量到 50 万。超过这个数基本可以断定是把"总建筑面积/规划面积/
# 多馆联动累计面积"填进了展览面积字段——东莞家具展的 100 万㎡ 就是这么来的。
# 这条是通识而非精确值，所以只用来"标记可疑"，不直接改数据。
AREA_SUSPECT_CEILING = 500_000

# 计算基准时，面积下限。几百平米的"展"通常是抓错了页面（抓到某个分论坛）。
AREA_MIN_USABLE = 3_000

# 品类内样本数达到这个数才单独出基准，否则回落父组。
# 3 是下限：2 个样本的"中位数"就是平均值，一个异常值就能带偏整组。
MIN_CATEGORY_SAMPLES = 3

# 父组（机械装备/消费品/食品医药…）的准入门槛比品类高，
# 因为父组把语义拉开了（鞋类和纺织服装算一组）。样本不够就别用。
MIN_PARENT_SAMPLES = 4

# 多路证据的收敛判定（最大值 ÷ 最小值）
FUSE_HIGH = 1.6      # 三路差 60% 以内 → high
FUSE_MID = 2.5       # 差 2.5 倍以内 → mid
FUSE_REJECT = 4.0    # 差 4 倍以上 → 不估

# 多路碰巧高度一致时，区间不能缩成 0。它们可能共享同一个错误假设，
# 一致 ≠ 正确。所以区间至少撑开到点值的 ±25%。
MIN_RELATIVE_SPREAD = 0.25

# 单路证据的区间倍数（没有第二路交叉，只能给宽区间）
SINGLE_PATH_LO = 0.62
SINGLE_PATH_HI = 1.60

# 同城同品类类比的面积可比窗口：两个展面积差在 1.6 倍以内才直接借数，
# 超出则按面积比缩放（缩放本身会引入误差，所以只在 ±3 倍内才用）
PEER_AREA_TOLERANCE = 1.6
PEER_AREA_MAX_SCALE = 3.0

# 同城同品类至少要这么多**不同**的实测展，才允许当参照。
#
# 2 不是随手定的。1 个样本的"中位数"就是那个样本本身，等于把另一个展的
# 规模直接抄过来——实际踩过两个荒谬结果：
#   · 上海国际汽车工业展览会 → 抄了汽配展（automechanika）的 7465 家展商，
#     车展和汽配展同属"车辆及配件"，但规模差着量级
#   · CAFEEX 咖啡展 → 抄了 SIAL 的 5000 家展商 / 20 万㎡
#     （SIAL 是全品类食品大展，咖啡展面积只有它的零头）
# 有 2 个独立展之后，"中位"才真的是中位；而且此时三路证据的收敛判定
# 才有意义（一路抄来的值不构成交叉验证）。
PEER_MIN_SAMPLES = 2


# ============================================================
# 数据结构
# ============================================================

@dataclass(frozen=True)
class Evidence:
    """一路证据。`basis` 要能让用户看懂"这个数是怎么来的"。"""

    path: str        # area / counter / peer
    value: float     # 这一路算出来的值
    basis: str       # 人话说明，直接上页面

    def to_dict(self) -> dict:
        return {"path": self.path, "value": self.value, "basis": self.basis}


@dataclass
class Estimate:
    """一个字段的估算结果。"""

    field_name: str
    value: int
    lo: int
    hi: int
    confidence: str          # high / mid / low
    evidence: list[Evidence] = field(default_factory=list)
    note: str = ""

    @property
    def spread(self) -> float:
        return round(self.hi / self.value, 2) if self.value else 0.0

    def to_dict(self) -> dict:
        return {
            "field": self.field_name,
            "value": self.value,
            "lo": self.lo,
            "hi": self.hi,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "note": self.note,
        }


@dataclass
class Benchmark:
    """
    估算基准：全部来自实测样本，逐项记录样本数以便复核。

    三层回退：**品类 → 品类父组 → 全样本**。

    为什么要有父组这一层：18 个品类里有 14 个的实测样本不足 3 个
    （"鞋类"只有 1 个、"礼品"只有 1 个），直接回落全样本会把
    "鞋类展"按"综合服务展"的密度估，误差白送。父组（机械装备/消费品/
    食品医药…）能把 3~4 个相近品类并起来，样本够了，语义也还站得住。

    但**父组也不是越大越好**：父组样本仍不足 MIN_PARENT_SAMPLES 时才回落全局，
    否则"纺织鞋服"4 个样本里 3 个是服装展，去估鞋类展照样跑偏。
    """

    density: float             # 展商密度：家 / 千㎡
    ratio: float               # 观众/展商比：人 / 家
    vdens: float               # 观众密度：人 / 千㎡
    n_samples: int
    by_category: dict[str, dict] = field(default_factory=dict)
    by_parent: dict[str, dict] = field(default_factory=dict)

    def for_category(self, category: Optional[str]) -> dict:
        """按 品类 → 父组 → 全局 的顺序取基准，并说明用了哪一层。"""
        hit = self.by_category.get(category or "")
        if hit:
            return {**hit, "level": "category", "source": f"{category}品类 {hit['n']} 个实测展"}

        parent = CATEGORY_PARENT_GROUPS.get(category or "")
        hit = self.by_parent.get(parent or "")
        if hit:
            return {
                **hit, "level": "parent",
                "source": f"{parent}大类 {hit['n']} 个实测展（{category}单独样本不足 {MIN_CATEGORY_SAMPLES} 个）",
            }

        return {
            "density": self.density,
            "ratio": self.ratio,
            "vdens": self.vdens,
            "n": self.n_samples,
            "level": "global",
            "source": f"全样本 {self.n_samples} 个实测展（{category}及其父组样本均不足）",
        }


# ============================================================
# 基准构建
# ============================================================

def _median_or(values: list[float], fallback: float) -> float:
    return statistics.median(values) if values else fallback


def normalize_row(r: dict) -> Optional[dict]:
    """
    把一行实测数据归一化成内部结构。

    两处要用同一份归一化结果：算基准、找同城同品类参照。
    早先这两处各写了一遍（基准用 `exhib`、参照用 `exhibitor_count`），
    结果同城那一路永远拿不到值——自检里"两路收敛应判 high"直接失败。
    所以抽出来，只此一份。

    归一化规则（每条都有理由，不要放宽）：
    - 人次 ÷ 2 折成人数，否则基准里的比值整体虚高一倍
    - **只接受 company 口径的展商数**。brand（品牌）实测密度 26.7、
      booth（展位）41.7、company 12.5——口径混进来会把基准抬高 2~3 倍
    - 面积低于 3 千平米视为抓错页面（抓到某个分论坛），高于 50 万㎡
      视为把总建筑面积填进了展览面积，两者都不进基准
    """
    area = r.get("exhibit_area_sqm") or 0
    area = float(area) if isinstance(area, (int, float)) else 0.0
    exhib = r.get("exhibitor_count") or 0
    visitor_raw = r.get("visitor_count") or 0
    vcal = (r.get("visitor_caliber") or "").lower()

    visitor = normalize_visitor_count(visitor_raw, vcal) if vcal else int(visitor_raw or 0)
    if visitor is None:
        return None

    if area < AREA_MIN_USABLE or area > AREA_SUSPECT_CEILING:
        return None
    if exhib <= 0:
        return None
    if (r.get("exhibitor_caliber") or "company").lower() != "company":
        return None

    return {
        "slug": r.get("slug"),
        "category": r.get("category"),
        "city": r.get("city"),
        "area": area,
        "exhib": float(exhib),
        "visitor": float(visitor),
    }


def build_benchmark(measured: Iterable[dict]) -> Benchmark:
    """
    从实测行构建基准。

    **只接受 company 口径的展商数**。brand（品牌）和 booth（展位）与
    company（企业）不是一回事：实测 brand 口径的密度是 26.7，booth 口径 41.7，
    company 口径 12.5——混进来会把基准整体抬高 2~3 倍，然后所有估算一起错。
    """
    rows = [x for x in (normalize_row(r) for r in measured) if x]

    if not rows:
        # 没有基准就不估。返回单位值让调用方的估算全部返回 None，
        # 好过抛异常把整个流水线停掉。
        return Benchmark(density=0.0, ratio=0.0, vdens=0.0, n_samples=0)

    densities = [r["exhib"] / (r["area"] / 1000) for r in rows]
    ratios = [r["visitor"] / r["exhib"] for r in rows if r["visitor"] > 0]
    vdens = [r["visitor"] / (r["area"] / 1000) for r in rows if r["visitor"] > 0]

    g_density = _median_or(densities, 0.0)
    g_ratio = _median_or(ratios, 0.0)
    g_vdens = _median_or(vdens, 0.0)

    # 分品类
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        if r["category"]:
            buckets.setdefault(r["category"], []).append(r)

    by_category: dict[str, dict] = {}
    for cat, items in buckets.items():
        if len(items) < MIN_CATEGORY_SAMPLES:
            continue
        cd = [i["exhib"] / (i["area"] / 1000) for i in items]
        cr = [i["visitor"] / i["exhib"] for i in items if i["visitor"] > 0]
        cv = [i["visitor"] / (i["area"] / 1000) for i in items if i["visitor"] > 0]
        by_category[cat] = {
            "density": _median_or(cd, g_density),
            "ratio": _median_or(cr, g_ratio),
            "vdens": _median_or(cv, g_vdens),
            "n": len(items),
        }

    # 父组基准
    by_parent: dict[str, dict] = {}
    p_buckets: dict[str, list[dict]] = {}
    for r in rows:
        parent = CATEGORY_PARENT_GROUPS.get(r["category"] or "")
        if parent:
            p_buckets.setdefault(parent, []).append(r)
    for parent, items in p_buckets.items():
        if len(items) < MIN_PARENT_SAMPLES:
            continue
        cd = [i["exhib"] / (i["area"] / 1000) for i in items]
        cr = [i["visitor"] / i["exhib"] for i in items if i["visitor"] > 0]
        cv = [i["visitor"] / (i["area"] / 1000) for i in items if i["visitor"] > 0]
        by_parent[parent] = {
            "density": _median_or(cd, g_density),
            "ratio": _median_or(cr, g_ratio),
            "vdens": _median_or(cv, g_vdens),
            "n": len(items),
        }

    return Benchmark(
        density=round(g_density, 2),
        ratio=round(g_ratio, 2),
        vdens=round(g_vdens, 1),
        n_samples=len(rows),
        by_category=by_category,
        by_parent=by_parent,
    )


# ============================================================
# 融合：多路证据 → 一个数
# ============================================================

def _round_to(value: float, step: int) -> int:
    """估算结果按量级取整。1247 家、38.42 万人这种数会让人以为是实测的。"""
    if value <= 0:
        return 0
    return max(step, int(round(value / step)) * step)


def _fuse(
    field_name: str,
    evidence: list[Evidence],
    step: int,
    note: str = "",
) -> Optional[Estimate]:
    """
    把几路证据合成一个估算值。合成规则刻意简单，因为复杂的加权无法解释。

    - 0 路 → None（不估）
    - 1 路 → 取该值，区间放宽到 0.62~1.60 倍，confidence=low
    - 多路 → 点值取中位数（不是平均：平均会被离群的那一路拽走），
      区间取 min~max 再撑开到至少 ±25%，confidence 看 max/min
    - max/min > 4.0 → None（证据互相否定，不能硬选一个）
    """
    if not evidence:
        return None

    values = [e.value for e in evidence if e.value > 0]
    if not values:
        return None

    if len(values) == 1:
        v = values[0]
        return Estimate(
            field_name=field_name,
            value=_round_to(v, step),
            lo=_round_to(v * SINGLE_PATH_LO, step),
            hi=_round_to(v * SINGLE_PATH_HI, step),
            confidence="low",
            evidence=evidence,
            note=(note + " " if note else "") + "仅一路证据，无交叉验证",
        )

    lo_v, hi_v = min(values), max(values)
    ratio = hi_v / lo_v if lo_v > 0 else 99.0

    if ratio > FUSE_REJECT:
        return None  # 证据互相否定：留空比选一个错的好

    mid = statistics.median(values)

    # 区间下限不能低于 mid*(1-MIN_SPREAD)，否则三路碰巧一致时会假装精确
    lo_floor = mid * (1 - MIN_RELATIVE_SPREAD)
    hi_ceil = mid * (1 + MIN_RELATIVE_SPREAD)
    lo_out = min(lo_v, lo_floor)
    hi_out = max(hi_v, hi_ceil)

    if ratio <= FUSE_HIGH:
        conf = "high"
    elif ratio <= FUSE_MID:
        conf = "mid"
    else:
        conf = "low"

    return Estimate(
        field_name=field_name,
        value=_round_to(mid, step),
        lo=_round_to(lo_out, step),
        hi=_round_to(hi_out, step),
        confidence=conf,
        evidence=evidence,
        note=note,
    )


# ============================================================
# 单展估算
# ============================================================

def _peer_evidence(
    rec: dict,
    field_key: str,
    peers: list[dict],
    rec_area: Optional[float],
) -> Optional[Evidence]:
    """
    同城同品类类比：拿同城同品类的实测展当参照。

    这是三条路里**最独立**的一条——它不依赖任何密度/比值换算，
    直接看"隔壁那个同类展是多少"。所以它对面积脏值免疫：
    东莞家具展的 100 万㎡ 影响不到"同城同品类中位数"。

    限制：
    - 同城同品类至少要 1 个实测展
    - 面积差 1.6 倍内直接借中位数；1.6~3 倍按面积比缩放；超 3 倍不用
      （2000㎡ 的展和 20 万㎡ 的展不是一个物种，缩放没有意义）
    """
    if not peers:
        return None
    values = [p[field_key] for p in peers if p.get(field_key)]
    if len(values) < PEER_MIN_SAMPLES:
        return None  # 单个样本不是参照，是复制

    base = statistics.median(values)
    peer_areas = [p["area"] for p in peers if p.get("area")]
    peer_area = statistics.median(peer_areas) if peer_areas else None

    if rec_area and peer_area:
        scale = rec_area / peer_area
        if scale > PEER_AREA_MAX_SCALE or scale < 1 / PEER_AREA_MAX_SCALE:
            return None  # 规模不在一个量级，借不了
        if abs(scale - 1) > (PEER_AREA_TOLERANCE - 1):
            scaled = base * scale
            return Evidence(
                path="peer",
                value=scaled,
                basis=f"同城同品类 {len(values)} 个实测展中位 {base:,.0f}，按面积比 {scale:.2f} 缩放",
            )

    return Evidence(
        path="peer",
        value=base,
        basis=f"同城同品类 {len(values)} 个实测展中位 {base:,.0f}（面积相当，直接借）",
    )


def estimate_one(
    rec: dict,
    bench: Benchmark,
    measured_norm: list[dict],
) -> dict[str, Estimate]:
    """
    对一个展的缺失字段做估算。

    入参 rec 需要有：category / city / visitor_count / exhibitor_count /
    exhibit_area_sqm / visitor_caliber / exhibitor_caliber。

    `measured_norm` 是**归一化后的实测集合**（`normalize_row` 的输出），
    用来找同城同品类参照。估算结果绝不回流进这个集合。

    返回 {field: Estimate}，估不出的字段不出现在字典里。
    """
    cat = rec.get("category")
    city = rec.get("city")
    b = bench.for_category(cat)

    density = b.get("density") or 0.0
    ratio = b.get("ratio") or 0.0
    vdens = b.get("vdens") or 0.0
    basis_src = b.get("source", "")

    area = rec.get("exhibit_area_sqm") or 0
    area_dirty = area > AREA_SUSPECT_CEILING
    area_use = area if (area >= AREA_MIN_USABLE and not area_dirty) else 0

    # 展商数：非 company 口径（brand / booth）**本身是实测值**，只是口径不同。
    # 不能拿它算密度（会把基准抬高 2~3 倍），但也不该给它估一个 company 数——
    # 那样页面上会同时出现"800 品牌"和一个估算的"560 家企业"，用户不知道该信哪个。
    # 有值就保留，只是不参与基准，也不触发估算。
    exhib_caliber = (rec.get("exhibitor_caliber") or "company").lower()
    exhib_raw = rec.get("exhibitor_count") or 0
    exhib_usable = exhib_caliber in ("company", "")
    exhib = exhib_raw if exhib_usable else 0

    # 观众数：口径是 registered / unknown 时 normalize 返回 None（不硬转）。
    # 这种情况下库里其实**有值**，只是折算不了；同样不估，留给前端如实显示口径。
    visitor_raw = rec.get("visitor_count") or 0
    vcal = (rec.get("visitor_caliber") or "").lower()
    visitor = normalize_visitor_count(visitor_raw, vcal) if vcal else (
        int(visitor_raw) if visitor_raw else 0
    )
    visitor_unusable = visitor is None or not visitor
    visitor = visitor or 0

    peers = [
        m for m in measured_norm
        if m.get("category") == cat and m.get("city") == city
    ]

    out: dict[str, Estimate] = {}
    dirty_note = "面积原值超单馆容量上限，估算时已弃用" if area_dirty else ""

    # ---- 展商数 ----
    if not exhib and not (exhib_raw and not exhib_usable):
        ev: list[Evidence] = []
        if area_use and density:
            ev.append(Evidence(
                "area", area_use / 1000 * density,
                f"面积 {area_use/10000:.1f} 万㎡ × 密度 {density:.1f} 家/千㎡（{basis_src}）",
            ))
        if visitor and ratio:
            ev.append(Evidence(
                "counter", visitor / ratio,
                f"观众 {visitor/10000:.1f} 万 ÷ 比值 {ratio:.0f} 人/家（{basis_src}）",
            ))
        p = _peer_evidence(rec, "exhib", peers, area_use)
        if p:
            ev.append(p)
        est = _fuse("exhibitor_count", ev, step=10, note=dirty_note)
        if est:
            out["exhibitor_count"] = est

    # ---- 观众数 ----
    if not visitor and not (visitor_raw and visitor_unusable):
        ev = []
        if exhib and ratio:
            ev.append(Evidence(
                "counter", exhib * ratio,
                f"展商 {exhib:,} 家 × 比值 {ratio:.0f} 人/家（{basis_src}）",
            ))
        if area_use and vdens:
            ev.append(Evidence(
                "area", area_use / 1000 * vdens,
                f"面积 {area_use/10000:.1f} 万㎡ × 观众密度 {vdens:.0f} 人/千㎡（{basis_src}）",
            ))
        p = _peer_evidence(rec, "visitor", peers, area_use)
        if p:
            ev.append(p)
        est = _fuse("visitor_count", ev, step=1000, note=dirty_note)
        if est:
            out["visitor_count"] = est

    # ---- 面积 ----
    if not area:
        ev = []
        if exhib and density:
            ev.append(Evidence(
                "counter", exhib / density * 1000,
                f"展商 {exhib:,} 家 ÷ 密度 {density:.1f} 家/千㎡（{basis_src}）",
            ))
        if visitor and vdens:
            ev.append(Evidence(
                "area", visitor / vdens * 1000,
                f"观众 {visitor/10000:.1f} 万 ÷ 观众密度 {vdens:.0f} 人/千㎡（{basis_src}）",
            ))
        # 同城同品类的展会面积是最直接的参照：同城同类展往往在同一个馆办，
        # 摊位的物理上限是同一个（广交会展馆装不下 85 万㎡）。
        # rec_area 传 0，因为这一路就是要估面积本身，没有面积可用来缩放。
        p = _peer_evidence(rec, "area", peers, 0)
        if p:
            ev.append(p)
        est = _fuse("exhibit_area_sqm", ev, step=500)
        if est:
            out["exhibit_area_sqm"] = est

    return out


def estimate_all(
    records: list[dict],
    measured: list[dict],
) -> tuple[dict[str, dict[str, Estimate]], Benchmark]:
    """
    对整批展做估算。返回 ({slug: {field: Estimate}}, benchmark)。

    `records` 是全部待估展（含已完整的），`measured` 是实测集合。
    已完整的展也会跑一遍——`estimate_one` 只对空字段出手，
    有值的字段不会被覆盖，所以对它们来说是空操作。
    """
    bench = build_benchmark(measured)
    norm = [x for x in (normalize_row(r) for r in measured) if x]
    result: dict[str, dict[str, Estimate]] = {}
    for rec in records:
        est = estimate_one(rec, bench, norm)
        if est:
            result[rec["slug"]] = est
    return result, bench


# ============================================================
# 自检
# ============================================================

def self_check() -> list[str]:
    """跑一遍不依赖数据库的断言，返回问题列表（空 = 通过）。"""
    issues: list[str] = []

    # 基准：4 个构造样本，密度分别 10/12/14/16 家/千㎡
    fake_measured = [
        {"category": "机械", "city": "上海", "exhibit_area_sqm": 100_000,
         "exhibitor_count": 1000, "visitor_count": 100_000,
         "visitor_caliber": "person", "exhibitor_caliber": "company"},
        {"category": "机械", "city": "上海", "exhibit_area_sqm": 100_000,
         "exhibitor_count": 1200, "visitor_count": 120_000,
         "visitor_caliber": "person", "exhibitor_caliber": "company"},
        {"category": "机械", "city": "北京", "exhibit_area_sqm": 100_000,
         "exhibitor_count": 1400, "visitor_count": 140_000,
         "visitor_caliber": "person", "exhibitor_caliber": "company"},
        {"category": "机械", "city": "北京", "exhibit_area_sqm": 100_000,
         "exhibitor_count": 1600, "visitor_count": 160_000,
         "visitor_caliber": "person", "exhibitor_caliber": "company"},
    ]
    b = build_benchmark(fake_measured)
    if b.n_samples != 4:
        issues.append(f"基准样本数应为 4，实际 {b.n_samples}")
    if abs(b.density - 13.0) > 0.01:
        issues.append(f"密度中位数应为 13.0，实际 {b.density}")
    if abs(b.ratio - 100.0) > 0.1:
        issues.append(f"比值中位数应为 100.0，实际 {b.ratio}")

    # 人次必须折算：报 20 万人次 = 10 万人，比值 100 而不是 200
    visit_row = dict(fake_measured[0])
    visit_row["visitor_caliber"] = "visit"
    visit_row["visitor_count"] = 200_000
    b2 = build_benchmark([visit_row])
    if abs(b2.ratio - 100.0) > 0.1:
        issues.append(f"人次口径未折算：比值应为 100，实际 {b2.ratio}")

    # brand 口径不得进基准
    brand_row = dict(fake_measured[0])
    brand_row["exhibitor_caliber"] = "brand"
    b3 = build_benchmark([brand_row])
    if b3.n_samples != 0:
        issues.append("brand 口径样本混进了基准，会整体抬高密度")

    # 面积脏值不得进基准
    dirty = dict(fake_measured[0])
    dirty["exhibit_area_sqm"] = 1_000_000
    b4 = build_benchmark([dirty])
    if b4.n_samples != 0:
        issues.append("超上限面积混进了基准")

    norm = [x for x in (normalize_row(r) for r in fake_measured) if x]

    # 单路证据 → low
    rec = {"slug": "t1", "category": "机械", "city": "广州",
           "exhibit_area_sqm": 100_000, "exhibitor_count": 0,
           "visitor_count": 0, "visitor_caliber": None, "exhibitor_caliber": None}
    est = estimate_one(rec, b, norm)
    if "exhibitor_count" not in est:
        issues.append("有面积应能估出展商数")
    elif est["exhibitor_count"].confidence != "low":
        issues.append(f"仅面积一路应为 low，实际 {est['exhibitor_count'].confidence}")

    # 三路一致 → high（面积、观众、同城同品类都指向 13 家/千㎡）
    rec2 = {"slug": "t2", "category": "机械", "city": "上海",
            "exhibit_area_sqm": 100_000, "exhibitor_count": 0,
            "visitor_count": 0, "visitor_caliber": None, "exhibitor_caliber": None}
    est2 = estimate_one(rec2, b, norm)
    # 上海只有 2 个同类展（1000/1200），中位 1100；面积路 1300 → 差 1.18 倍 → high
    if "exhibitor_count" in est2 and est2["exhibitor_count"].confidence != "high":
        issues.append(
            f"面积+同城两路收敛应判 high，实际 {est2['exhibitor_count'].confidence}"
        )

    # 证据互相否定 → 不估（两路差 50 倍，说明基准不成立）
    evs = [Evidence("area", 100, "x"), Evidence("peer", 5000, "y")]
    if _fuse("x", evs, 1) is not None:
        issues.append("两路差 50 倍居然给了估算值，应该拒绝")

    # 估算值不得覆盖实测
    full = {"slug": "t3", "category": "机械", "city": "上海",
            "exhibit_area_sqm": 100_000, "exhibitor_count": 999,
            "visitor_count": 88888, "visitor_caliber": "person",
            "exhibitor_caliber": "company"}
    est3 = estimate_one(full, b, norm)
    if est3:
        issues.append(f"字段已齐全的展不该产生估算，实际产生 {list(est3)}")

    return issues
