"""
智能匹配工作流 (Match Workflow)

把「智能推荐」从散落的规则函数重构为一条**显式的多阶段工作流**，每个阶段
职责单一、可观测（耗时/候选数/说明/因子分值写入 trace）、可降级（全链路零云依赖）：

    S0 画像装配  ── 展商画像（行业领域+展品品类+关键词+价格带+地域+历史热度）
    │               或采购需求画像（标题/描述/品类/预算/地域/历史热度）
    S1 多路召回  ── 品类通道 + 关键词倒排通道（IDF 加权），合并去重
    S2 候选过滤  ── 状态/自单/已应标剔除
    S3 多信号打分── **恰好 5 个因子**（行业30 · 产品30 · 地域15 · 预算15 · 历史行为10）
    S4 排序截断  ── 加权总分降序 + 阈值门控 + Top-K
    S5 解释生成  ── 本地模板生成五因子中文推荐理由（无 LLM）

LLM 仅作为可选的「AI 解读」增强（由 /api/ai 承担），失败/超时自动降级到
S5 的本地解释，不影响主链路。

设计约束：
- 纯本地：无网络调用、无新增数据库表（jieba 为可选依赖，缺失自动降级）
- 进程级缓存：语料（分词/IDF/倒排）与展商画像都按「数据库版本指纹」缓存，
  变更自动重建；浏览/收藏计数变化不触发重建（聚合值就地刷新，口径不变）
- 参数集中：权重/阈值集中在文件头部常量，便于调参与演示讲解
- 打分口径：各因子先算 0~1 相似度 → × 固定权重（合计 100）→ 四舍五入到 0~100；
  数据缺失用「中性 0.5」占位而不是把权重摊给其他因子（避免缺字段被放大）
"""
from __future__ import annotations

import copy
import math
import re
import threading
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from fastapi import APIRouter
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.catalog import CatalogExhibitor
from app.models.exhibition import Exhibition
from app.models.favorite import Favorite
from app.models.micro_booth import MicroBooth
from app.models.procurement import Procurement
from app.models.procurement_match import ProcurementMatch
from app.models.product import Product
from app.models.user import User
from app.models.venue import Venue
from app.modules.matching.textkit import (
    IdfModel,
    build_query,
    build_title_query,
    category_affinity,
    expand_recall_tokens,
    keyword_coverage_tiered,
    normalize_category,
    token_hit,
    tokenize,
)

# ============================================================
# 工作流参数（唯一调参入口）
# ============================================================

# ---- 撮合打分权重：恰好 5 个因子，合计恒为 100 分（写死为常量）----
#
# 权重为什么这么定（2026-10 改造）：
# 1) 行业 30 + 产品 30 = 60 分：撮合的本质是"这家展商到底能不能做这类东西"。
#    行业（行业领域/展品品类 ↔ 需求品类）对"跨体系品类写法"鲁棒（空调/家用电器），
#    产品（关键词 IDF 覆盖 + 展品池命中）对细粒度需求敏感，两者互补且都是强判别
#    证据，因此各占 30 分，构成总分主体。
# 2) 地域 15：线下撮合的成交成本与地域强相关（看样/物流/售后），但展商可跨地域
#    供货，地域只是"更愿意"而非"能不能"，故权重低于行业/产品。
# 3) 预算 15：预算与价格带是否重叠决定"能不能谈"，但真实数据预算/价格缺失率高
#    （本库 procurements 全部未填预算），给 15 分防止单字段决定排序。
# 4) 历史行为 10：浏览/收藏/应标是结果侧信号，滞后且易被运营刷量影响，只作 10 分
#    微调项，保证冷启动（全 0）时上限 90 分而不是直接判低。
# 5) 取消原 freshness（新鲜度）独立因子：新鲜度与"是否匹配"无因果关系，且会让
#    老需求被永久降权；原 keyword(0.38) + portfolio(0.10) 合并进 product(30) 内部
#    按 0.7/0.3 加权；原 category(0.32) 更名 industry(30)。
WEIGHTS_EXHIBITOR: dict[str, float] = {
    "industry": 30.0,   # 行业：展商行业领域/展品品类 ↔ 采购需求品类
    "product": 30.0,    # 产品：0.7×关键词 IDF 覆盖 + 0.3×展品池命中
    "region": 15.0,     # 地域：同城 100% / 同省异城 60% / 跨省 0 / 缺失中性 50%
    "budget": 15.0,     # 预算：预算区间 ↔ 展品价格带
    "history": 10.0,    # 历史行为：展商热度 + 需求热度（对数归一化）
}

# 采购需求 ← 展品 方向：同样恰好 5 个因子，语义一一对应
# （行业=需求品类↔展品品类；产品=关键词覆盖+展品名精度；地域=展品/展商所在地；
#   预算=预算↔展品价格；历史行为=展品热度+需求热度）
WEIGHTS_PRODUCT: dict[str, float] = {
    "industry": 30.0,
    "product": 30.0,
    "region": 15.0,
    "budget": 15.0,
    "history": 10.0,
}

# 硬约束：两套权重必须是同一组 5 个因子且合计 100（改权重必须同步改断言）
assert set(WEIGHTS_EXHIBITOR) == set(WEIGHTS_PRODUCT) == {
    "industry", "product", "region", "budget", "history",
}, "权重必须恰好包含 industry/product/region/budget/history 五个因子"
assert sum(WEIGHTS_EXHIBITOR.values()) == 100.0, "WEIGHTS_EXHIBITOR 合计必须为 100"
assert sum(WEIGHTS_PRODUCT.values()) == 100.0, "WEIGHTS_PRODUCT 合计必须为 100"

# 产品因子内部拆分：原 keyword(0.38) + portfolio(0.10) 合并后按 0.7/0.3 加权
PRODUCT_KEYWORD_SHARE = 0.7
PRODUCT_PORTFOLIO_SHARE = 0.3
PORTFOLIO_FULL_COUNT = 3.0        # 3 个相关展品 = 展品池"全覆盖"
HISTORY_FULL_SCALE = 500.0        # 展商侧热度参考量（≈500 次浏览/收藏 = 满分 1.0）
DEMAND_HISTORY_FULL_SCALE = 10.0  # 需求侧热度参考量（≈10 次应标/收藏 = 满分 1.0）
NEUTRAL_SIMILARITY = 0.5          # 数据缺失时的中性相似度：缺数据 ≠ 不匹配，不惩罚

# 地域因子档位（需求：同城满分 / 同省异城 60% / 跨省 0 / 任一侧缺失 中性 50%）
REGION_SAME_CITY = 1.0
REGION_SAME_PROVINCE = 0.6
REGION_DIFF_PROVINCE = 0.0

# match_level 阈值（需求：≥70 high / ≥40 medium / 其余 low）
LEVEL_HIGH = 70
LEVEL_MEDIUM = 40

SAME_EXHIBITION_BONUS = 0.20  # 同一展会上下文对行业信号的加成
NOTIFY_MIN_SCORE = 55         # 发布采购时给展商推送通知的最低匹配度（独立于 match_level）
TEXT_SNIPPET = 80             # 展品描述参与分词的截断长度（控制缓存构建成本）
MAX_KW_RECALL = 400           # 关键词通道召回上限（保护延迟）

# ============================================================
# 地域解析：省/市两级（不引入第三方行政区划库）
# ============================================================
#
# 平台里的地域字符串形态不统一：users.region 可能是"广东省深圳市"/"深圳"，
# exhibitions.location 形如"佛山 · 潭洲国际会展中心"，venues.city / 名录
# catalog_exhibitors.city 则是裸城市名（"深圳"）。这里用一张**平台数据内出现过的
# 城市 → 省**常量表把裸城市名补全为省级归属；未覆盖的城市降级为城市级比较
# （判定不了省就给中性 50%，只在能证明"跨省"时才给 0）。
CITY_PROVINCE: dict[str, str] = {
    # 直辖市（省 == 市）
    "北京": "北京", "上海": "上海", "天津": "天津", "重庆": "重庆",
    # 广东
    "广州": "广东", "深圳": "广东", "东莞": "广东", "佛山": "广东", "珠海": "广东",
    "中山": "广东", "惠州": "广东", "汕头": "广东", "江门": "广东", "湛江": "广东",
    # 江苏
    "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏", "南通": "江苏",
    "徐州": "江苏", "昆山": "江苏", "常熟": "江苏", "张家港": "江苏",
    # 浙江
    "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "台州": "浙江", "玉环": "浙江",
    "金华": "浙江", "绍兴": "浙江", "嘉兴": "浙江", "义乌": "浙江", "湖州": "浙江",
    # 山东
    "济南": "山东", "青岛": "山东", "烟台": "山东", "潍坊": "山东", "临沂": "山东",
    # 福建
    "福州": "福建", "厦门": "福建", "泉州": "福建",
    # 东北
    "沈阳": "辽宁", "大连": "辽宁", "鞍山": "辽宁",
    "长春": "吉林", "哈尔滨": "黑龙江", "大庆": "黑龙江",
    # 华北
    "石家庄": "河北", "唐山": "河北", "太原": "山西", "呼和浩特": "内蒙古",
    # 华中
    "郑州": "河南", "洛阳": "河南", "武汉": "湖北", "宜昌": "湖北",
    "长沙": "湖南", "株洲": "湖南",
    # 西南
    "成都": "四川", "绵阳": "四川", "昆明": "云南", "贵阳": "贵州", "拉萨": "西藏",
    "南宁": "广西", "桂林": "广西",
    # 西北
    "西安": "陕西", "咸阳": "陕西", "兰州": "甘肃", "西宁": "青海",
    "银川": "宁夏", "乌鲁木齐": "新疆",
    # 港澳台
    "香港": "香港", "澳门": "澳门", "台北": "台湾",
}

_MUNICIPALITIES = ("北京", "上海", "天津", "重庆")
_PROVINCE_NAMES = tuple(sorted(set(CITY_PROVINCE.values()), key=len, reverse=True))
_CITY_NAMES = tuple(sorted(CITY_PROVINCE, key=len, reverse=True))
_REGION_PUNCT_RE = re.compile(r"[\s·•・|｜/\\、,，;；:：()（）\[\]【】\-—]+")
_CITY_SUFFIX_RE = re.compile(r"(自治州|地区|盟|市|省|特别行政区)$")
_REGION_CITY_RE = re.compile(r"^([\u4e00-\u9fff]{2,4})")


def _normalize_region(raw: Any) -> str:
    """地域字符串归一化：去空格/分隔符/括号（"佛山 · 潭洲国际会展中心" → "佛山潭洲国际会展中心"）。"""
    if raw is None:
        return ""
    return _REGION_PUNCT_RE.sub("", str(raw).strip().lower())


def _parse_region(raw: Any) -> Optional[tuple[str, str]]:
    """把任意地域字符串解析成 (省, 市)；解析不出来返回 None（调用方按"数据缺失"处理）。

    纯拉丁/英文地名不做猜测 → 返回 None（宁可中性也不误判跨省）。
    """
    s = _normalize_region(raw)
    if not s:
        return None
    if s.isascii():  # 英文城市名不在常量表内，不做猜测
        return None
    province = next((p for p in _PROVINCE_NAMES if p in s), "")
    rest = s
    if province:
        idx = s.find(province)
        tail = s[idx + len(province):]
        rest = tail or s
    city = next((c for c in _CITY_NAMES if c in rest), "")
    if not city:
        city = next((c for c in _CITY_NAMES if c in s), "")
    if not city:
        m = _REGION_CITY_RE.match(rest)
        if m and rest and rest not in _PROVINCE_NAMES:
            city = m.group(1)
    if not city and province in _MUNICIPALITIES:
        city = province
    if city:
        city = _CITY_SUFFIX_RE.sub("", city)
    if not province:
        province = CITY_PROVINCE.get(city, "")
    if not province and not city:
        return None
    return (province, city)


def _region_compare(a: tuple[str, str], b: tuple[str, str]) -> tuple[float, str]:
    """单对地域比较 → (相似度, 中文口径)。"""
    (pa, ca), (pb, cb) = a, b
    if ca and ca == cb:
        return REGION_SAME_CITY, "地域同城"
    if pa and pb:
        if pa == pb:
            return REGION_SAME_PROVINCE, "地域同省"
        return REGION_DIFF_PROVINCE, "地域跨省"
    return NEUTRAL_SIMILARITY, "地域信息不足（中性计）"


def _region_factor(
    candidate_regions: Iterable[tuple[str, str]],
    demand_regions: Iterable[tuple[str, str]],
) -> tuple[float, str]:
    """地域因子：取两侧地域集合的**最优配对**（展商可多地参展，买家可多地需求）。

    任一侧为空 → 中性 50%（不惩罚数据缺失）；配对结果里有同城即同城。
    """
    cands = list(candidate_regions or ())
    demands = list(demand_regions or ())
    if not cands or not demands:
        return NEUTRAL_SIMILARITY, "地域数据缺失（中性计）"
    best_v, best_label = REGION_DIFF_PROVINCE, "地域跨省"
    for a in cands:
        for b in demands:
            value, label = _region_compare(a, b)
            if value > best_v:
                best_v, best_label = value, label
    return best_v, best_label


# ============================================================
# 数据结构的补充上下文（批量预取，避免逐条打分的 N+1）
# ============================================================

@dataclass
class DemandContext:
    """需求侧上下文：每条采购需求的地域（省/市）与历史热度（0~1）。

    由 `_demand_context(db, ids)` 一次性批量装配，打分函数只读本对象，不再查库。
    """
    regions: dict[int, list[tuple[str, str]]] = field(default_factory=dict)
    history: dict[int, float] = field(default_factory=dict)

    def region_of(self, procurement_id: Optional[int]) -> list[tuple[str, str]]:
        return self.regions.get(int(procurement_id), []) if procurement_id else []

    def history_of(self, procurement_id: Optional[int]) -> float:
        if not procurement_id:
            return NEUTRAL_SIMILARITY
        return self.history.get(int(procurement_id), NEUTRAL_SIMILARITY)


@dataclass
class ProductSideContext:
    """展品方向上下文：需求侧（固定一条）+ 候选展品所属展商/展会的地域。"""
    demand_id: Optional[int] = None
    demand_regions: list[tuple[str, str]] = field(default_factory=list)
    demand_history: float = NEUTRAL_SIMILARITY
    exhibitor_regions: dict[int, list[tuple[str, str]]] = field(default_factory=dict)
    exhibition_regions: dict[int, list[tuple[str, str]]] = field(default_factory=dict)

    def regions_of_product(self, exhibitor_id: Any, exhibition_id: Any) -> list[tuple[str, str]]:
        """候选侧地域 = 展品所属展会城市 + 展商（账号/微展位/名录）所在地，去重合并。"""
        out: list[tuple[str, str]] = []
        if exhibition_id:
            out.extend(self.exhibition_regions.get(int(exhibition_id), []))
        if exhibitor_id:
            out.extend(self.exhibitor_regions.get(int(exhibitor_id), []))
        seen: set[tuple[str, str]] = set()
        uniq: list[tuple[str, str]] = []
        for r in out:
            if r not in seen:
                seen.add(r)
                uniq.append(r)
        return uniq


def _exhibition_regions(db: Session, exhibition_ids: Iterable[Any]) -> dict[int, list[tuple[str, str]]]:
    """展会 → 地域：优先展馆城市（venues.city），回退展会 location 前缀。"""
    ids = [int(i) for i in exhibition_ids if i]
    if not ids:
        return {}
    rows = (
        db.query(Exhibition.id, Exhibition.location, Venue.city)
        .outerjoin(Venue, Venue.id == Exhibition.venue_id)
        .filter(Exhibition.id.in_(ids))
        .all()
    )
    out: dict[int, list[tuple[str, str]]] = {}
    for eid, location, venue_city in rows:
        bucket: list[tuple[str, str]] = []
        for raw in (venue_city, location):
            parsed = _parse_region(raw)
            if parsed and parsed not in bucket:
                bucket.append(parsed)
        out[int(eid)] = bucket
    return out


def _exhibitor_regions(db: Session, user_ids: Iterable[Any]) -> dict[int, list[tuple[str, str]]]:
    """展商 → 地域集合：users.region + 微展位所属展会城市 + 微展位关联名录展商城市。"""
    ids = [int(i) for i in user_ids if i]
    if not ids:
        return {}
    out: dict[int, list[tuple[str, str]]] = {i: [] for i in ids}
    for uid, region in db.query(User.id, User.region).filter(User.id.in_(ids)).all():
        parsed = _parse_region(region)
        if parsed and parsed not in out[int(uid)]:
            out[int(uid)].append(parsed)
    rows = (
        db.query(MicroBooth.exhibitor_id, Exhibition.location, Venue.city, CatalogExhibitor.city)
        .outerjoin(Exhibition, Exhibition.id == MicroBooth.exhibition_id)
        .outerjoin(Venue, Venue.id == Exhibition.venue_id)
        .outerjoin(CatalogExhibitor, CatalogExhibitor.id == MicroBooth.catalog_exhibitor_id)
        .filter(MicroBooth.exhibitor_id.in_(ids))
        .all()
    )
    for uid, location, venue_city, catalog_city in rows:
        bucket = out[int(uid)]
        for raw in (venue_city, location, catalog_city):
            parsed = _parse_region(raw)
            if parsed and parsed not in bucket:
                bucket.append(parsed)
    return out


def _demand_context(db: Session, procurement_ids: Iterable[Any]) -> DemandContext:
    """批量装配需求侧上下文（地域 + 历史热度）：4 条 SQL，与候选条数无关。"""
    ids = sorted({int(i) for i in procurement_ids if i})
    ctx = DemandContext()
    if not ids:
        return ctx
    rows = (
        db.query(Procurement.id, Procurement.purchaser_id, Procurement.exhibition_id)
        .filter(Procurement.id.in_(ids))
        .all()
    )
    purchaser_ids = {int(r[1]) for r in rows if r[1]}
    purchaser_regions: dict[int, Any] = {}
    if purchaser_ids:
        for uid, region in db.query(User.id, User.region).filter(User.id.in_(purchaser_ids)).all():
            purchaser_regions[int(uid)] = region
    exhibition_regions = _exhibition_regions(db, {r[2] for r in rows if r[2]})

    match_counts: dict[int, int] = {
        int(pid): int(cnt)
        for pid, cnt in db.query(ProcurementMatch.procurement_id, func.count(ProcurementMatch.id))
        .filter(ProcurementMatch.procurement_id.in_(ids))
        .group_by(ProcurementMatch.procurement_id)
        .all()
    }
    fav_counts: dict[int, int] = {
        int(eid): int(cnt)
        for eid, cnt in db.query(Favorite.entity_id, func.count(Favorite.id))
        .filter(
            Favorite.entity_type.in_(("procurement", "procurements")),
            Favorite.entity_id.in_(ids),
        )
        .group_by(Favorite.entity_id)
        .all()
    }
    for pid, purchaser_id, exhibition_id in rows:
        bucket: list[tuple[str, str]] = []
        if purchaser_id:
            parsed = _parse_region(purchaser_regions.get(int(purchaser_id)))
            if parsed:
                bucket.append(parsed)
        if exhibition_id:
            for parsed in exhibition_regions.get(int(exhibition_id), []):
                if parsed not in bucket:
                    bucket.append(parsed)
        pid = int(pid)
        ctx.regions[pid] = bucket
        ctx.history[pid] = _demand_history(match_counts.get(pid, 0), fav_counts.get(pid, 0))
    return ctx


# ============================================================
# 数据结构
# ============================================================

@dataclass
class StageTrace:
    """工作流单阶段运行记录（供 API 返回与前端展示）。"""
    name: str
    ms: float
    count_in: int = 0
    count_out: int = 0
    note: str = ""
    detail: dict[str, Any] = field(default_factory=dict)  # 五因子分值等结构化细节

    def as_dict(self) -> dict[str, Any]:
        out = {
            "name": self.name,
            "ms": round(self.ms, 2),
            "in": self.count_in,
            "out": self.count_out,
            "note": self.note,
        }
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass
class MatchOutcome:
    """工作流运行结果：推荐条目 + 阶段 trace + 汇总元信息。"""
    items: list[dict[str, Any]] = field(default_factory=list)
    trace: list[StageTrace] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        return {"engine": "match-workflow-local", "version": "1.0", **self.meta,
                "stages": [s.as_dict() for s in self.trace]}


@dataclass
class ExhibitorProfile:
    """展商画像（S0 产出）。"""
    user_id: int
    cats: set[str] = field(default_factory=set)
    tokens: Counter = field(default_factory=Counter)
    token_set: set[str] = field(default_factory=set)
    text: str = ""
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    booth_score: float = 0.0
    exhibition_ids: set[int] = field(default_factory=set)
    product_token_sets: list[set[str]] = field(default_factory=list)
    regions: list[tuple[str, str]] = field(default_factory=list)  # 展商地域（省, 市）集合
    history: float = 0.0     # 展商侧历史热度 0~1（对数归一）
    history_raw: float = 0.0  # 原始计数：Σ products.view_count + Σ micro_booths.favorite_count


@dataclass
class FactorScore:
    """单个因子的打分中间态：相似度(0~1) → 权重 → 整数分值（Σ 分值 == 总分）。"""
    key: str
    similarity: float
    label: str = ""
    weight: float = 0.0
    points: int = 0

    @property
    def raw(self) -> float:
        return self.weight * self.similarity


FACTOR_ORDER = ("industry", "product", "region", "budget", "history")
FACTOR_NAMES = {
    "industry": "行业",
    "product": "产品",
    "region": "地域",
    "budget": "预算",
    "history": "历史行为",
}


# ============================================================
# 五因子合并 / 取整 / 中文解释（S3 · S5）
# ============================================================

def _clamp01(value: Any) -> float:
    """容错转 0~1 相似度：None/非数值/NaN → 中性 0.5，越界截断。"""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return NEUTRAL_SIMILARITY
    if x != x:  # NaN
        return NEUTRAL_SIMILARITY
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _combine_factors(
    factors: list[FactorScore],
    weights: dict[str, float],
) -> tuple[int, dict[str, int]]:
    """固定权重 × 0~1 相似度 → 总分（0~100 四舍五入）+ 每因子整数分值。

    权重合计恒为 100，所以**不做**"按可用权重归一化"：数据缺失用中性 0.5 占位，
    仍然占据它那份权重（缺字段不会被其他因子放大，也不会被按 0 分惩罚）。
    每因子分值用最大余数法取整，保证 Σ 分项 == 总分（解释行与总分永远对得上）。
    """
    raws: list[float] = []
    raw_total = 0.0
    for f in factors:
        f.weight = float(weights.get(f.key, 0.0))
        f.similarity = _clamp01(f.similarity)
        raw = f.weight * f.similarity
        raws.append(raw)
        raw_total += raw
    score = int(round(raw_total))
    score = 0 if score < 0 else (100 if score > 100 else score)

    floors = [int(math.floor(r)) for r in raws]
    rest = score - sum(floors)
    if rest > 0 and floors:
        order = sorted(range(len(raws)), key=lambda i: raws[i] - floors[i], reverse=True)
        for i in range(rest):
            floors[order[i % len(order)]] += 1
    for f, points in zip(factors, floors):
        f.points = int(points)
    return score, {f.key: f.points for f in factors}


def _signals_of(factors: Iterable[FactorScore]) -> dict[str, Optional[float]]:
    """把因子相似度导出为 signals（键名与旧代码对齐：五因子 key）。"""
    return {f.key: f.similarity for f in factors}


def _explain_factors(factors: list[FactorScore], score: int) -> str:
    """S5 解释模板（中文五因子口径）：总分行 = Σ 分项，与 match_score 完全一致。"""
    parts = [
        f"{f.label} +{f.points}（{int(round(f.weight))}%×{f.similarity:.2f}）"
        for f in factors
    ]
    return f"匹配度 {score}（满分100）｜" + "；".join(parts)


def _brief_factors(points: dict[str, int], score: int) -> str:
    """精简五因子行（通知正文等窄场景）：行业 +30 · 产品 +26 · …（合计 92）。"""
    if not points:
        return "综合匹配"
    body = " · ".join(
        f"{FACTOR_NAMES.get(key, key)} +{int(points.get(key, 0))}" for key in FACTOR_ORDER
    )
    return f"{body}（合计 {int(round(score))}）"


def _industry_label(value: float, has_data: bool) -> str:
    if not has_data:
        return "行业数据缺失（中性计）"
    if value >= 1.0:
        return "行业精确匹配"
    if value >= 0.6:
        return "行业同大类"
    return "行业跨类"


def _budget_factor(value: Optional[float]) -> tuple[float, str]:
    """预算因子：区间重叠 1.0 / 有偏差 0.25 / 数据缺失 中性 0.5。"""
    if value is None:
        return NEUTRAL_SIMILARITY, "预算数据缺失（中性计）"
    v = _clamp01(value)
    if v >= 1.0:
        return 1.0, "预算在区间内"
    return v, "预算与价格带有偏差"


def _history_label(value: float) -> str:
    if value >= 0.66:
        return "历史热度高"
    if value >= 0.33:
        return "历史热度中等"
    if value > 0:
        return "历史热度偏低"
    return "历史热度暂无"


def _log_norm(raw: Any, full_scale: float) -> float:
    """历史热度对数归一化到 0~1：full_scale 次视为满分，0 次为 0。"""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value <= 0 or full_scale <= 0:
        return 0.0
    return min(1.0, math.log1p(value) / math.log1p(full_scale))


def _demand_history(match_count: Any, fav_count: Any) -> float:
    """需求侧历史行为：已有应标(match)数 + 被收藏数 → 0~1；完全没有历史 → 中性 0.5。"""
    try:
        raw = float(match_count or 0) + float(fav_count or 0)
    except (TypeError, ValueError):
        return NEUTRAL_SIMILARITY
    if raw <= 0:
        return NEUTRAL_SIMILARITY
    return _log_norm(raw, DEMAND_HISTORY_FULL_SCALE)


def _keyword_stats(
    core_query: dict[str, int],
    extra_query: dict[str, int],
    doc_text: str,
    doc_tokens: set[str],
    idf: IdfModel,
) -> tuple[float, list[str], int, int]:
    """关键词覆盖 → (0~1 覆盖度, 命中词, 命中词数, 参与匹配词数)。"""
    value, hits = keyword_coverage_tiered(core_query, extra_query, doc_text, doc_tokens, idf)
    merged = dict(core_query)
    for t, w in extra_query.items():
        merged[t] = max(merged.get(t, 0), w)
    covered = sum(1 for t in merged if token_hit(t, doc_text, doc_tokens) > 0)
    return value, hits, covered, len(merged)


def _name_coverage(core_query: dict[str, int], name: Optional[str]) -> float:
    """展品名命中精度：核心词在展品名称内的加权覆盖率 0~1（容错，名称缺失记 0）。"""
    if not core_query or not name:
        return 0.0
    text = str(name).lower()
    tokens = set(tokenize(text))
    num = 0.0
    den = 0.0
    for tok, weight in core_query.items():
        den += weight
        num += weight * token_hit(tok, text, tokens)
    return 0.0 if den <= 0 else min(1.0, num / den)


# ============================================================
# 进程级缓存：语料（分词/IDF/倒排）+ 展商画像
# ============================================================
#
# 为什么需要（2026-10 真实库实测：products 67,357 / micro_booths 5,000）：
# - 语料冷构建 ~7.2s：jieba 分词 4.7s + IDF 0.26s + 取数 0.6s；
# - build_exhibitor_profile(大展商) ~7.6s：6.7 万行展品 + 5,000 个微展位逐条装配，
#   其中微展位 jieba 分词 ~4.9s。
# 两者都在每次撮合里重算，score_pair 因此稳定在 8s 量级。下面把它们做成进程级缓存。
#
# ── 缓存键（数据版本指纹）──────────────────────────────────────
# 版本指纹用廉价聚合查询算：
#   products      : (count, max(id), max(updated_at))  [仅 status='published']
#   micro_booths  : (count, max(id), max(updated_at))
#   profile 额外带该展商侧的 (sum(view_count), sum(favorite_count), max(views+3*favs))
#   profile 还带 user.industry_domain / user.region（画像只读这两个用户字段）
#
# ── 为什么还要「行级内容复核」──────────────────────────────────
# analytics 的 page_view 会写 Product.view_count（app/modules/analytics/analytics.py:65），
# 而 Product.updated_at 带 onupdate=func.now() —— 一次浏览就会推进 max(updated_at)。
# 若把 updated_at 当成唯一版本，缓存会被浏览流量击穿（仍然 7s/次，正是要修的现象）。
# 所以：指纹负责「触发复核」，真正决定重建的是行级复核——
#   把 updated_at > 水位的行取回来逐行比对内容（展品 text/品类/价格/展会/状态；
#   微展位 行业领域/名称/简介/场馆城市），内容真变了才重建；只有浏览/曝光/收藏
#   计数变了 → 只推进版本水位，继续用缓存。
#   计数类字段不进内容签名，而是用指纹里的聚合值就地刷新画像的 history / booth_score，
#   公式与逐行累加逐位一致（log1p 单调 ⇒ max(log1p(x)) == log1p(max(x))）。
#
# ── 并发 ──────────────────────────────────────────────────────
# FastAPI 同步端点跑在线程池里：缓存读写走 _CACHE_LOCK；7s 级构建走独立构建锁在锁外
# 进行（双检 + 后写胜出），不会把所有请求串行化。

_CACHE_LOCK = threading.RLock()          # 保护 _CORPUS / _PROFILE_CACHE / 版本水位
_CORPUS_BUILD_LOCK = threading.Lock()    # 语料构建串行（防并发重复构建 7s）
_PROFILE_BUILD_LOCK = threading.Lock()   # 画像构建串行（同上）
_STATS_LOCK = threading.Lock()           # 命中/构建统计

_REVALIDATE_MAX_ROWS = 256   # 单次行级复核最多取回多少条改动行；超过直接重建（防批量导入）
_PROFILE_CACHE_MAX = 8       # 画像缓存条目上限（LRU）；大展商单条约数十 MB

_CACHE_STATS: dict[str, Any] = {
    "hits": 0,
    "misses": 0,
    "build_ms": 0.0,
    "corpus": {"hits": 0, "misses": 0, "build_ms": 0.0},
    "profile": {"hits": 0, "misses": 0, "build_ms": 0.0},
}


def _cache_stat(kind: str, *, hit: bool, build_ms: float = 0.0) -> None:
    """记录一次缓存命中/构建（线程安全，只做加法，不查库）。"""
    with _STATS_LOCK:
        slot = "hits" if hit else "misses"
        _CACHE_STATS[slot] += 1
        bucket = _CACHE_STATS[kind]
        bucket[slot] += 1
        if not hit:
            _CACHE_STATS["build_ms"] += float(build_ms)
            bucket["build_ms"] += float(build_ms)


def cache_stats() -> dict[str, Any]:
    """当前进程的缓存观测快照（公开只读，不查库、不写库）。"""
    with _STATS_LOCK:
        snapshot = {
            "hits": int(_CACHE_STATS["hits"]),
            "misses": int(_CACHE_STATS["misses"]),
            "build_ms": round(float(_CACHE_STATS["build_ms"]), 3),
            "corpus": dict(_CACHE_STATS["corpus"]),
            "profile": dict(_CACHE_STATS["profile"]),
        }
    with _CACHE_LOCK:
        corpus_size = 1 if _CORPUS is not None else 0
        profile_size = len(_PROFILE_CACHE)
    for kind in ("corpus", "profile"):
        snapshot[kind]["build_ms"] = round(float(snapshot[kind]["build_ms"]), 3)
    snapshot["corpus"]["size"] = corpus_size
    snapshot["profile"]["size"] = profile_size
    snapshot["size"] = corpus_size + profile_size
    return snapshot


class _Corpus:
    def __init__(self, version: tuple, built_at: float):
        self.version = version          # 构建时 _data_version() 的返回值
        self.built_at = built_at
        self.prod_tokens: dict[int, set[str]] = {}
        self.prod_text: dict[int, str] = {}
        self.prod_cat: dict[int, str] = {}
        self.idf: Optional[IdfModel] = None
        self.inverted: dict[str, set[int]] = {}

    def age_seconds(self) -> float:
        """缓存已存活秒数（仅观测用，不作失效条件）。"""
        return time.time() - self.built_at


_CORPUS: Optional[_Corpus] = None


def _data_version(db: Session) -> tuple:
    """廉价数据版本指纹：products + micro_booths 各 1 条聚合 SQL。

    返回 ``(products.count, products.max_id, products.max_updated_at,
    micro_booths.count, micro_booths.max_id, micro_booths.max_updated_at)``。
    6.7 万行实测 ~50-80ms（updated_at 无索引，必须扫表；count/max(id) 走索引近乎免费）。
    """
    p = (
        db.query(
            func.count(Product.id),
            func.max(Product.id),
            func.max(Product.updated_at),
        )
        .filter(Product.status == "published")
        .one()
    )
    b = (
        db.query(
            func.count(MicroBooth.id),
            func.max(MicroBooth.id),
            func.max(MicroBooth.updated_at),
        )
        .one()
    )
    return (int(p[0] or 0), int(p[1] or 0), p[2], int(b[0] or 0), int(b[1] or 0), b[2])


def _corpus_is_current(db: Session, corpus: _Corpus, version: tuple) -> bool:
    """语料是否仍可用于该版本；必要时推进水位（不重建）。

    版本变了先按行复核内容：只有展品「内容」真的变了才需要重建分词/IDF/倒排。
    """
    if version == corpus.version:
        return True
    old = corpus.version
    if version[0] != old[0] or version[1] != old[1]:
        return False  # 展品增删 / 上下架：分词集合与 IDF 都要重算
    if version[2] == old[2]:
        # 只是 micro_booths 侧变了：语料只依赖 products，直接推进版本
        with _CACHE_LOCK:
            corpus.version = version
        return True
    if version[2] is None:
        return False
    rows = (
        db.query(Product.id, Product.name, Product.description, Product.category, Product.status)
        .filter(Product.updated_at > old[2])
        .limit(_REVALIDATE_MAX_ROWS + 1)
        .all()
    )
    if len(rows) > _REVALIDATE_MAX_ROWS:
        return False  # 批量改动，直接重建
    for pid, name, desc, cat, status in rows:
        if status != "published":
            return False  # 下架 → 语料必须剔除
        text = f"{name or ''} {(desc or '')[:TEXT_SNIPPET]}".lower()
        if corpus.prod_text.get(int(pid)) != text:
            return False
        if corpus.prod_cat.get(int(pid)) != normalize_category(cat):
            return False
    # 内容没变，只是浏览/曝光计数推进了 updated_at → 推进水位，继续用缓存
    with _CACHE_LOCK:
        corpus.version = version
    return True


def _build_corpus(db: Session, version: tuple) -> _Corpus:
    corpus = _Corpus(version, time.time())
    rows = (
        db.query(Product.id, Product.name, Product.description, Product.category)
        .filter(Product.status == "published")
        .all()
    )
    docs: list[list[str]] = []
    texts: list[str] = []
    for pid, name, desc, cat in rows:
        text = f"{name or ''} {(desc or '')[:TEXT_SNIPPET]}".lower()
        toks = tokenize(text)
        ncat = normalize_category(cat)
        if ncat:
            toks.append(ncat)  # 归一化品类作为一个强 token 参与关键词覆盖
        token_set = set(toks)
        corpus.prod_tokens[pid] = token_set
        corpus.prod_text[pid] = text
        corpus.prod_cat[pid] = ncat
        docs.append(toks)
        texts.append(text)
    corpus.idf = IdfModel(docs, texts)
    for pid, toks in corpus.prod_tokens.items():
        for t in toks:
            corpus.inverted.setdefault(t, set()).add(pid)
    return corpus


def get_corpus(db: Session) -> _Corpus:
    """获取产品语料（分词/IDF/倒排）：进程内按数据版本缓存，内容变更才重建。"""
    global _CORPUS
    version = _data_version(db)
    cur = _CORPUS
    if cur is not None and _corpus_is_current(db, cur, version):
        _cache_stat("corpus", hit=True)
        return cur
    with _CORPUS_BUILD_LOCK:
        cur = _CORPUS
        version = _data_version(db)  # 等锁期间数据可能又变了，重新取版本
        if cur is not None and _corpus_is_current(db, cur, version):
            _cache_stat("corpus", hit=True)
            return cur
        t0 = time.perf_counter()
        built = _build_corpus(db, version)
        with _CACHE_LOCK:
            _CORPUS = built
        _cache_stat("corpus", hit=False, build_ms=(time.perf_counter() - t0) * 1000)
        return built


def invalidate_corpus() -> None:
    """显式失效语料 + 展商画像缓存（测试/数据批量导入后调用）。"""
    global _CORPUS
    with _CACHE_LOCK:
        _CORPUS = None
        _PROFILE_CACHE.clear()


# ------------------------------------------------------------
# 展商画像缓存（按 user_id，带版本指纹）
# ------------------------------------------------------------

@dataclass
class _ProfileEntry:
    """一份画像缓存：版本指纹 + 构建时的逐行内容签名（供行级复核）。"""
    version: tuple
    profile: "ExhibitorProfile"
    prod_sig: dict[int, tuple]   # pid -> (text, 归一化品类, price, exhibition_id)
    booth_sig: dict[int, tuple]  # bid -> (行业领域, 名称, 简介, 场馆城市, location, 名录城市)
    built_at: float


_PROFILE_CACHE: "OrderedDict[int, _ProfileEntry]" = OrderedDict()


def _profile_cache_get(user_id: int) -> Optional[_ProfileEntry]:
    with _CACHE_LOCK:
        entry = _PROFILE_CACHE.get(user_id)
        if entry is not None:
            _PROFILE_CACHE.move_to_end(user_id)  # LRU：命中即刷新
        return entry


def _profile_cache_put(user_id: int, entry: _ProfileEntry) -> None:
    with _CACHE_LOCK:
        _PROFILE_CACHE[user_id] = entry
        _PROFILE_CACHE.move_to_end(user_id)
        while len(_PROFILE_CACHE) > _PROFILE_CACHE_MAX:
            _PROFILE_CACHE.popitem(last=False)  # 淘汰最久未用


def _profile_version(db: Session, user: User) -> tuple:
    """展商画像的版本指纹（该展商侧 2 条聚合 SQL + user 上 2 个字段）。

    布局（下标固定，供 _profile_content_same 使用）：
      0 user_id | 1 industry_domain | 2 region
      3 展品 count | 4 展品 max_id | 5 展品 max_updated_at | 6 Σ展品 view_count
      7 微展位 count | 8 微展位 max_id | 9 微展位 max_updated_at
      10 Σ微展位 favorite_count | 11 max(views + 3*favs)
    其中 6/10/11 是计数类（易变）字段，不算内容，用于就地刷新 history/booth_score。
    """
    uid = int(user.id)
    p = (
        db.query(
            func.count(Product.id),
            func.max(Product.id),
            func.max(Product.updated_at),
            func.coalesce(func.sum(Product.view_count), 0),
        )
        .filter(Product.exhibitor_id == uid, Product.status == "published")
        .one()
    )
    b = (
        db.query(
            func.count(MicroBooth.id),
            func.max(MicroBooth.id),
            func.max(MicroBooth.updated_at),
            func.coalesce(func.sum(MicroBooth.favorite_count), 0),
            func.max(
                func.coalesce(MicroBooth.view_count, 0)
                + 3.0 * func.coalesce(MicroBooth.favorite_count, 0)
            ),
        )
        .filter(MicroBooth.exhibitor_id == uid)
        .one()
    )
    return (
        uid,
        str(getattr(user, "industry_domain", "") or ""),
        str(getattr(user, "region", "") or ""),
        int(p[0] or 0), int(p[1] or 0), p[2], int(p[3] or 0),
        int(b[0] or 0), int(b[1] or 0), b[2], int(b[3] or 0),
        None if b[4] is None else float(b[4]),
    )


def _profile_content_same(a: tuple, b: tuple) -> bool:
    """只比较「内容」字段（排除 6/10/11 三个计数类字段）。"""
    idx = (0, 1, 2, 3, 4, 5, 7, 8, 9)
    return tuple(a[i] for i in idx) == tuple(b[i] for i in idx)


def _profile_is_current(db: Session, entry: _ProfileEntry, version: tuple) -> bool:
    """画像是否仍可用；内容没变（只有计数变化）时推进版本，返回 True。"""
    old = entry.version
    if _profile_content_same(version, old):
        with _CACHE_LOCK:
            entry.version = version
        return True
    # 用户画像字段 / 展品增删上下架 / 微展位增删 → 语义变了，必须重建
    if (version[0:3] != old[0:3]
            or version[3] != old[3] or version[4] != old[4]
            or version[7] != old[7] or version[8] != old[8]):
        return False
    if not _profile_rows_unchanged(db, entry, version):
        return False
    with _CACHE_LOCK:
        entry.version = version
    return True


def _profile_rows_unchanged(db: Session, entry: _ProfileEntry, version: tuple) -> bool:
    """把 updated_at > 水位的展品/微展位取回来逐行比对内容签名（不重建）。"""
    uid = int(version[0])
    if version[5] != entry.version[5]:
        rows = (
            db.query(Product.id, Product.name, Product.description, Product.category,
                     Product.price, Product.exhibition_id, Product.status)
            .filter(Product.exhibitor_id == uid, Product.updated_at > entry.version[5])
            .limit(_REVALIDATE_MAX_ROWS + 1)
            .all()
        )
        if len(rows) > _REVALIDATE_MAX_ROWS:
            return False
        for pid, name, desc, cat, price, exh_id, status in rows:
            if status != "published":
                return False
            sig = entry.prod_sig.get(int(pid))
            if sig is None:
                return False
            text = f"{name or ''} {(desc or '')[:TEXT_SNIPPET]}".lower()
            price_f = None if price is None else float(price)
            exh_i = int(exh_id) if exh_id else None
            if sig != (text, normalize_category(cat), price_f, exh_i):
                return False
    if version[9] != entry.version[9]:
        rows = (
            db.query(MicroBooth.id, MicroBooth.industry_domain, MicroBooth.name,
                     MicroBooth.description, Exhibition.location, Venue.city,
                     CatalogExhibitor.city)
            .outerjoin(Exhibition, Exhibition.id == MicroBooth.exhibition_id)
            .outerjoin(Venue, Venue.id == Exhibition.venue_id)
            .outerjoin(CatalogExhibitor, CatalogExhibitor.id == MicroBooth.catalog_exhibitor_id)
            .filter(MicroBooth.exhibitor_id == uid, MicroBooth.updated_at > entry.version[9])
            .limit(_REVALIDATE_MAX_ROWS + 1)
            .all()
        )
        if len(rows) > _REVALIDATE_MAX_ROWS:
            return False
        for bid, ind, bname, bdesc, location, venue_city, catalog_city in rows:
            sig = entry.booth_sig.get(int(bid))
            if sig is None or sig != (ind, bname, bdesc, venue_city, location, catalog_city):
                return False
    return True


def _profile_apply_volatile(profile: ExhibitorProfile, version: tuple) -> ExhibitorProfile:
    """用指纹里的计数聚合就地刷新 history / booth_score（与重建逐位一致）。

    重建口径：
      history_raw = Σint(products.view_count) + Σint(micro_booths.favorite_count)
      history     = _log_norm(history_raw, HISTORY_FULL_SCALE)
      booth_score = max over booths of min(1, log1p(views + 3*favs) / log1p(500))
    因为 log1p 单调，max(log1p(x)) == log1p(max(x))，所以聚合值可完全复现。
    """
    view_sum = int(version[6] or 0)
    fav_sum = int(version[10] or 0)
    max_pop = version[11]
    history_raw = float(view_sum + fav_sum)
    history = _log_norm(history_raw, HISTORY_FULL_SCALE)
    booth_score = 0.0 if max_pop is None else min(
        1.0, math.log1p(float(max_pop)) / math.log1p(500.0)
    )
    if (profile.history_raw == history_raw and profile.history == history
            and profile.booth_score == booth_score):
        return profile  # 计数没变：直接复用同一对象（零拷贝）
    refreshed = copy.copy(profile)  # 浅拷贝：大字段（text/token）共享，只改 3 个标量
    refreshed.history_raw = history_raw
    refreshed.history = history
    refreshed.booth_score = booth_score
    return refreshed


# ============================================================
# 工具
# ============================================================

def _age_days(dt: Optional[datetime], now: datetime) -> Optional[float]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def _budget_signal(
    budget_min: Optional[float],
    budget_max: Optional[float],
    price_min: Optional[float],
    price_max: Optional[float],
) -> Optional[float]:
    """预算区间与价格带吻合度：重叠 1.0 / 有差距 0.25 / 数据缺失 None。"""
    if budget_min is None and budget_max is None:
        return None
    if price_min is None and price_max is None:
        return None
    lo_b = budget_min if budget_min is not None else budget_max
    hi_b = budget_max if budget_max is not None else budget_min
    lo_p = price_min if price_min is not None else price_max
    hi_p = price_max if price_max is not None else price_min
    assert lo_b is not None and hi_b is not None and lo_p is not None and hi_p is not None
    if hi_p < lo_b or lo_p > hi_b:
        return 0.25
    return 1.0


def _level(score: float) -> str:
    if score >= LEVEL_HIGH:
        return "high"
    if score >= LEVEL_MEDIUM:
        return "medium"
    return "low"


# ============================================================
# S0 画像装配
# ============================================================

def _build_exhibitor_profile_uncached(
    db: Session,
    user: User,
    corpus: Optional[_Corpus] = None,
) -> tuple[ExhibitorProfile, dict[int, tuple], dict[int, tuple], bool]:
    """真正的画像装配（无缓存）：行业领域 + 展品品类/关键词/价格带 + 微展位地域/热度 + 历史热度。

    返回 ``(profile, prod_sig, booth_sig, cacheable)``。``prod_sig`` / ``booth_sig`` 是
    逐行内容签名（不含浏览/收藏计数），供缓存命中时做行级复核；``cacheable=False``
    表示装配过程中命中了「语料里没有该展品」的兜底分词路径，结果不进缓存。
    """
    profile = ExhibitorProfile(user_id=user.id)
    prod_sig: dict[int, tuple] = {}
    booth_sig: dict[int, tuple] = {}
    cacheable = True
    if user.industry_domain:
        nc = normalize_category(user.industry_domain)
        if nc:
            profile.cats.add(nc)
    parsed_region = _parse_region(getattr(user, "region", None))
    if parsed_region:
        profile.regions.append(parsed_region)

    corpus = corpus if corpus is not None else get_corpus(db)
    prods = (
        db.query(Product.id, Product.category, Product.price, Product.exhibition_id,
                 Product.view_count)
        .filter(Product.exhibitor_id == user.id, Product.status == "published")
        .all()
    )
    texts: list[str] = []
    product_views = 0
    for pid, cat, price, exh_id, view_count in prods:
        nc = normalize_category(cat)
        if nc:
            profile.cats.add(nc)
        toks = corpus.prod_tokens.get(pid)
        if toks is None:  # 语料指纹竞态兜底：现场分词
            toks = set(tokenize(f"{cat or ''}"))
            cacheable = False
        for t in toks:
            profile.tokens[t] += 2
        profile.product_token_sets.append(toks)
        price_f: Optional[float] = None
        if price is not None:
            price_f = float(price)
            profile.price_min = price_f if profile.price_min is None else min(profile.price_min, price_f)
            profile.price_max = price_f if profile.price_max is None else max(profile.price_max, price_f)
        exh_i: Optional[int] = None
        if exh_id:
            exh_i = int(exh_id)
            profile.exhibition_ids.add(exh_i)
        product_views += int(view_count or 0)
        text = corpus.prod_text.get(pid, "")
        texts.append(text)
        prod_sig[int(pid)] = (text, nc, price_f, exh_i)

    booths = (
        db.query(MicroBooth.id, MicroBooth.industry_domain, MicroBooth.name,
                 MicroBooth.description, MicroBooth.view_count, MicroBooth.favorite_count,
                 Exhibition.location, Venue.city, CatalogExhibitor.city)
        .outerjoin(Exhibition, Exhibition.id == MicroBooth.exhibition_id)
        .outerjoin(Venue, Venue.id == Exhibition.venue_id)
        .outerjoin(CatalogExhibitor, CatalogExhibitor.id == MicroBooth.catalog_exhibitor_id)
        .filter(MicroBooth.exhibitor_id == user.id)
        .all()
    )
    booth_favs = 0
    for bid, ind, bname, bdesc, views, favs, location, venue_city, catalog_city in booths:
        booth_sig[int(bid)] = (ind, bname, bdesc, venue_city, location, catalog_city)
        if ind:
            nc = normalize_category(ind)
            if nc:
                profile.cats.add(nc)
        for t in tokenize(f"{bname or ''} {bdesc or ''}"):
            profile.tokens[t] += 1
        pop = math.log1p(float(views or 0) + 3.0 * float(favs or 0))
        profile.booth_score = max(profile.booth_score, min(1.0, pop / math.log1p(500.0)))
        booth_favs += int(favs or 0)
        for raw in (venue_city, location, catalog_city):
            parsed = _parse_region(raw)
            if parsed and parsed not in profile.regions:
                profile.regions.append(parsed)

    # 展商侧历史行为：products.view_count + micro_booths.favorite_count，对数归一
    profile.history_raw = float(product_views + booth_favs)
    profile.history = _log_norm(profile.history_raw, HISTORY_FULL_SCALE)

    profile.text = " ".join(texts)
    profile.token_set = set(profile.tokens)
    profile.cats.discard("")
    return profile, prod_sig, booth_sig, cacheable


def build_exhibitor_profile(
    db: Session,
    user: User,
    corpus: Optional[_Corpus] = None,
) -> ExhibitorProfile:
    """展商画像（S0）：按 user_id 进程内缓存，数据版本变了自动重建。

    命中时若只有浏览/收藏计数变了，用版本指纹里的聚合值就地刷新
    history / booth_score（公式与重建逐位一致），不重建 7s 级画像。
    ``corpus`` 可由调用方传入已取到的语料，省掉一次版本探测。
    """
    uid = getattr(user, "id", None)
    if uid is None:  # 未落库的用户对象：不做缓存
        profile, _ps, _bs, _ok = _build_exhibitor_profile_uncached(db, user, corpus)
        return profile
    uid = int(uid)
    version = _profile_version(db, user)
    entry = _profile_cache_get(uid)
    if entry is not None and _profile_is_current(db, entry, version):
        _cache_stat("profile", hit=True)
        return _profile_apply_volatile(entry.profile, version)
    with _PROFILE_BUILD_LOCK:
        entry = _profile_cache_get(uid)
        version = _profile_version(db, user)  # 等锁期间数据可能又变了
        if entry is not None and _profile_is_current(db, entry, version):
            _cache_stat("profile", hit=True)
            return _profile_apply_volatile(entry.profile, version)
        t0 = time.perf_counter()
        profile, prod_sig, booth_sig, cacheable = _build_exhibitor_profile_uncached(db, user, corpus)
        build_ms = (time.perf_counter() - t0) * 1000
        if cacheable:
            _profile_cache_put(uid, _ProfileEntry(
                version=version, profile=profile,
                prod_sig=prod_sig, booth_sig=booth_sig, built_at=time.time(),
            ))
        _cache_stat("profile", hit=False, build_ms=build_ms)
        return profile


# ============================================================
# 方向一：展商 ← 采购需求
# ============================================================

def _score_procurement_for_profile(
    p: Procurement,
    profile: ExhibitorProfile,
    idf: IdfModel,
    now: datetime,
    ctx: Optional[DemandContext] = None,
) -> tuple[float, dict[str, Optional[float]], list[str], dict[str, Any]]:
    """对单条采购需求打分（S3）。返回 (总分, 因子相似度, 理由, 附加信息)。

    五因子固定权重：industry 30 · product 30 · region 15 · budget 15 · history 10。
    """
    ctx = ctx or DemandContext()
    details: list[str] = []
    factors: list[FactorScore] = []

    # ---- 1) 行业 industry（原 category 更名，30 分）----
    pcat = normalize_category(p.category)
    raw_cat = 0.0
    if pcat:
        for c in profile.cats:
            aff = category_affinity(c, pcat)
            if aff is not None:
                raw_cat = max(raw_cat, aff)
    if pcat and profile.cats:
        ind_v = raw_cat
        if p.exhibition_id and int(p.exhibition_id) in profile.exhibition_ids:
            ind_v = min(1.0, ind_v + SAME_EXHIBITION_BONUS)
        factors.append(FactorScore("industry", ind_v, _industry_label(ind_v, True)))
        if raw_cat >= 1.0:
            details.append(f"品类精确匹配：{p.category}")
        elif raw_cat >= 0.6:
            details.append(f"同大类匹配（{pcat}）")
    else:
        factors.append(FactorScore("industry", NEUTRAL_SIMILARITY,
                                   _industry_label(0.0, False)))

    # ---- 2) 产品 product = 0.7 关键词覆盖 + 0.3 展品池命中（30 分）----
    core_query = build_title_query(p.title, 3)
    extra_query = build_query([(p.description, 1)])
    kw_v, hits, covered, total = _keyword_stats(
        core_query, extra_query, profile.text, profile.token_set, idf,
    )
    probe_tokens = set(hits) or {
        t for t, _ in sorted(core_query.items(), key=lambda kv: -idf.idf(kv[0]))[:5]
    }
    related_products = sum(1 for toks in profile.product_token_sets if toks & probe_tokens)
    portfolio_v = (
        min(1.0, related_products / PORTFOLIO_FULL_COUNT)
        if profile.product_token_sets else NEUTRAL_SIMILARITY
    )
    prod_v = PRODUCT_KEYWORD_SHARE * kw_v + PRODUCT_PORTFOLIO_SHARE * portfolio_v
    prod_label = f"产品关键词命中 {covered}/{total}"
    if related_products:
        prod_label += f" · 相关展品 {related_products} 个"
    factors.append(FactorScore("product", prod_v, prod_label))
    if hits:
        details.append("关键词命中：" + "、".join(hits))
    if related_products >= 2:
        details.append(f"与你 {related_products} 个展品相关")

    # ---- 3) 地域 region（15 分）----
    reg_v, reg_label = _region_factor(profile.regions, ctx.region_of(p.id))
    factors.append(FactorScore("region", reg_v, reg_label))

    # ---- 4) 预算 budget（15 分）----
    budget_v, budget_label = _budget_factor(_budget_signal(
        p.budget_min, p.budget_max, profile.price_min, profile.price_max,
    ))
    factors.append(FactorScore("budget", budget_v, budget_label))
    if budget_v >= 1.0:
        details.append("预算区间与展品价格带吻合")

    # ---- 5) 历史行为 history = 展商侧热度 50% + 需求侧热度 50%（10 分）----
    demand_heat = ctx.history_of(p.id)
    hist_v = 0.5 * profile.history + 0.5 * demand_heat
    factors.append(FactorScore("history", hist_v, _history_label(hist_v)))

    age = _age_days(p.created_at, now)
    if age is not None and age <= 5.0:
        details.append(f"{int(age)} 天前发布")

    # ---- 门控：关键词零命中且无相关展品 → 判为不匹配（保原逻辑，不进入五因子加权）----
    # 注意：门控判定在五因子算完之后，保证 trace/诊断里仍能看到 5 个因子各自的相似度
    if not hits and related_products == 0:
        return 0.0, _signals_of(factors), [], {
            "related_products": 0,
            "factors": {key: 0 for key in FACTOR_ORDER},
            "gated": True,
        }

    score, points = _combine_factors(factors, WEIGHTS_EXHIBITOR)
    reasons = [_explain_factors(factors, score)] + details[:4]
    return float(score), _signals_of(factors), reasons, {
        "related_products": related_products,
        "factors": points,
    }


def match_procurements_for_exhibitor(
    db: Session,
    user: User,
    limit: int = 10,
) -> MatchOutcome:
    """展商侧工作流：为展商推荐匹配的采购需求。"""
    t_start = time.perf_counter()
    now = datetime.now(timezone.utc)
    trace: list[StageTrace] = []

    # S0 画像装配
    t0 = time.perf_counter()
    profile = build_exhibitor_profile(db, user)
    trace.append(StageTrace(
        "S0 画像装配", (time.perf_counter() - t0) * 1000, count_out=len(profile.cats),
        note=(f"品类 {len(profile.cats)} / 关键词 {len(profile.tokens)} / "
              f"展品 {len(profile.product_token_sets)} / 地域 {len(profile.regions)} / "
              f"历史热度 {profile.history:.2f}"),
    ))

    # S1 多路召回：品类通道 + 关键词通道（pending 需求规模小，全量扫描）
    t0 = time.perf_counter()
    corpus = get_corpus(db)
    idf = corpus.idf
    assert idf is not None
    candidates = (
        db.query(Procurement)
        .filter(Procurement.status == "pending")
        .order_by(Procurement.created_at.desc())
        .limit(500)
        .all()
    )
    recalled_cat = recalled_kw = 0
    merged: dict[int, str] = {}
    for p in candidates:
        pcat = normalize_category(p.category)
        in_cat = bool(pcat and profile.cats and any(
            (category_affinity(c, pcat) or 0) > 0 for c in profile.cats
        ))
        kw_v, _ = keyword_coverage_tiered(
            build_title_query(p.title, 3), build_query([(p.description, 1)]),
            profile.text, profile.token_set, idf,
        )
        in_kw = kw_v > 0
        recalled_cat += 1 if in_cat else 0
        recalled_kw += 1 if in_kw else 0
        if in_cat or in_kw:
            merged[p.id] = "both" if (in_cat and in_kw) else ("cat" if in_cat else "kw")
    trace.append(StageTrace(
        "S1 多路召回", (time.perf_counter() - t0) * 1000,
        count_in=len(candidates), count_out=len(merged),
        note=f"品类通道 {recalled_cat} + 关键词通道 {recalled_kw} → 去重 {len(merged)}",
    ))

    # S2 过滤：剔除自家发布 / 已应标
    t0 = time.perf_counter()
    my_bids = {
        row[0] for row in db.query(ProcurementMatch.procurement_id)
        .filter(ProcurementMatch.exhibitor_id == user.id).all()
    }
    filtered = [
        p for p in candidates
        if p.id in merged and p.purchaser_id != user.id and p.id not in my_bids
    ]
    trace.append(StageTrace(
        "S2 候选过滤", (time.perf_counter() - t0) * 1000,
        count_in=len(merged), count_out=len(filtered),
        note=f"剔除自家发布/已应标 {len(merged) - len(filtered)} 条",
    ))

    # S3 打分（五因子，固定权重）
    t0 = time.perf_counter()
    demand_ctx = _demand_context(db, [p.id for p in filtered])
    scored: list[tuple[float, int, Procurement, list[str], dict[str, int]]] = []
    for p in filtered:
        score, _signals, reasons, extra = _score_procurement_for_profile(
            p, profile, idf, now, demand_ctx,
        )
        if score <= 0:
            continue
        scored.append((
            score, int(extra.get("related_products", 0)), p, reasons,
            extra.get("factors", {}),
        ))
    trace.append(StageTrace(
        "S3 五因子打分", (time.perf_counter() - t0) * 1000,
        count_in=len(filtered), count_out=len(scored),
        note="行业30 + 产品30 + 地域15 + 预算15 + 历史行为10（合计 100）",
        detail={
            "weights": {k: int(v) for k, v in WEIGHTS_EXHIBITOR.items()},
            "gate": "产品关键词零命中且无相关展品 → 0 分（不参与加权）",
        },
    ))

    # S4 排序截断（含冷启动兜底）
    t0 = time.perf_counter()
    scored.sort(key=lambda x: (-x[0], -x[1], -(x[2].id or 0)))
    top: list[tuple[float, int, Procurement, list[str], dict[str, int]]] = scored[:limit]
    if not top:
        top = [(1.0, 0, p, ["最新发布"], {}) for p in candidates[:limit]]
    items = [
        {
            "id": p.id, "title": p.title, "description": p.description,
            "category": p.category, "budget_min": p.budget_min, "budget_max": p.budget_max,
            "status": p.status, "purchaser_name": p.purchaser_name,
            "score": int(round(score)), "match_score": int(round(score)),
            "match_level": _level(score), "reasons": reasons,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for score, _rel, p, reasons, _f in top
    ]
    trace.append(StageTrace(
        "S4 排序截断", (time.perf_counter() - t0) * 1000,
        count_in=len(scored), count_out=len(items), note=f"Top-{limit} 阈值门控",
    ))

    # S5 解释生成（本地模板，五因子中文口径）
    t0 = time.perf_counter()
    trace.append(StageTrace(
        "S5 解释生成", (time.perf_counter() - t0) * 1000,
        count_in=len(items), count_out=len(items),
        note="中文五因子解释：总分行 = Σ 分项（行业/产品/地域/预算/历史行为）",
        detail={
            "factor_avg_top": (
                {
                    key: round(sum(int(f.get(key, 0)) for *_x, f in top) / len(top), 2)
                    for key in FACTOR_ORDER
                } if top else {}
            ),
            "samples": [
                {
                    "id": p.id,
                    "match_score": int(round(score)),
                    "factors": f,
                    "explain": reasons[0] if reasons else "",
                }
                for score, _rel, p, reasons, f in top[:3]
            ],
        },
    ))

    total_ms = (time.perf_counter() - t_start) * 1000
    return MatchOutcome(
        items=items, trace=trace,
        meta={"recalled": len(merged), "scored": len(scored), "returned": len(items),
              "total_ms": round(total_ms, 2)},
    )


def notify_exhibitor_matches(db: Session, procurement: Procurement) -> list[dict[str, Any]]:
    """发布采购后：对全部展商跑工作流，返回达到通知阈值的 (展商, 分数, 理由) Top5。"""
    now = datetime.now(timezone.utc)
    exhibitors = (
        db.query(User)
        .filter(User.role == "exhibitor", User.status == "active")
        .all()
    )
    corpus = get_corpus(db)
    assert corpus.idf is not None
    demand_ctx = _demand_context(db, [procurement.id])
    hits: list[dict[str, Any]] = []
    for user in exhibitors:
        if user.id == procurement.purchaser_id:
            continue
        try:
            profile = build_exhibitor_profile(db, user, corpus)
            if not profile.cats and not profile.tokens:
                continue
            score, _signals, reasons, extra = _score_procurement_for_profile(
                procurement, profile, corpus.idf, now, demand_ctx,
            )
            if score >= NOTIFY_MIN_SCORE:
                # 通知正文用精简五因子行（完整中文解释仍保留在 reasons[0]，供接口展示）
                hits.append({
                    "user_id": user.id,
                    "score": score,
                    "reason": _brief_factors(extra.get("factors", {}), score),
                    "explain": reasons[0] if reasons else "综合匹配",
                })
        except Exception:  # 单个展商画像失败不影响整体通知
            continue
    hits.sort(key=lambda x: -x["score"])
    return hits[:5]


def score_pair(
    db: Session,
    user: User,
    procurement: Procurement,
) -> dict[str, Any]:
    """诊断入口（只读）：给「展商 × 采购需求」一对打印五因子明细。

    仅用于自检/排障，不接入 API；返回结构含每因子的权重/相似度/整数分值，
    并保证 ``sum(factors.values()) == score``。
    """
    corpus = get_corpus(db)
    profile = build_exhibitor_profile(db, user, corpus)
    assert corpus.idf is not None
    ctx = _demand_context(db, [procurement.id])
    score, signals, reasons, extra = _score_procurement_for_profile(
        procurement, profile, corpus.idf, datetime.now(timezone.utc), ctx,
    )
    factors = extra.get("factors", {})
    return {
        "score": int(round(score)),
        "match_level": _level(score),
        "factors": factors,
        "factor_sum": int(sum(factors.values())),
        "signals": signals,
        "weights": {k: int(v) for k, v in WEIGHTS_EXHIBITOR.items()},
        "reasons": reasons,
        "explain": reasons[0] if reasons else "",
        "related_products": extra.get("related_products", 0),
        "exhibitor_region": profile.regions,
        "exhibitor_history": round(profile.history, 4),
        "demand_region": ctx.region_of(procurement.id),
        "demand_history": round(ctx.history_of(procurement.id), 4),
    }


def latest_pending_procurement(db: Session, user_id: int) -> Optional[Procurement]:
    """买家侧工作流入口：取该买家最新一条待匹配采购需求。"""
    return (
        db.query(Procurement)
        .filter(Procurement.purchaser_id == user_id, Procurement.status == "pending")
        .order_by(Procurement.created_at.desc())
        .first()
    )


def score_procurements_for_exhibitor(
    db: Session,
    user: User,
    procurement_ids: list[int],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    """对指定采购需求逐条打分（列表页匹配度徽章/排序用）。

    返回 ``(评分表 {procurement_id: {match_score, match_level, reasons}}, meta)``。
    """
    t_start = time.perf_counter()
    now = datetime.now(timezone.utc)
    corpus = get_corpus(db)
    profile = build_exhibitor_profile(db, user, corpus)
    idf = corpus.idf
    assert idf is not None
    procs = (
        db.query(Procurement).filter(Procurement.id.in_(procurement_ids)).all()
        if procurement_ids else []
    )
    demand_ctx = _demand_context(db, [p.id for p in procs])
    result: dict[int, dict[str, Any]] = {}
    for p in procs:
        score, _signals, reasons, _extra = _score_procurement_for_profile(
            p, profile, idf, now, demand_ctx,
        )
        result[p.id] = {
            "match_score": int(round(score)),
            "match_level": _level(score),
            "reasons": reasons,
        }
    meta = {
        "engine": "match-workflow-local", "version": "1.0",
        "scored": len(result), "total_ms": round((time.perf_counter() - t_start) * 1000, 2),
        "stages": [
            StageTrace(
                "S3 五因子打分", 0.0, count_in=len(procs), count_out=len(result),
                note="行业30 + 产品30 + 地域15 + 预算15 + 历史行为10（合计 100）",
                detail={"weights": {k: int(v) for k, v in WEIGHTS_EXHIBITOR.items()}},
            ).as_dict(),
        ],
    }
    return result, meta


# ============================================================
# 方向二：采购需求 ← 展品
# ============================================================

def _score_product_for_procurement(
    row: Any,
    core_query: dict[str, int],
    extra_query: dict[str, int],
    pcat: str,
    budget_min: Optional[float],
    budget_max: Optional[float],
    proc_exhibition_id: Optional[int],
    corpus: _Corpus,
    idf: IdfModel,
    now: datetime,
    ctx: Optional[ProductSideContext] = None,
) -> tuple[float, dict[str, Optional[float]], list[str], dict[str, Any]]:
    """对单个展品打分（S3）。row 为展品字段行（见 match_products_for_procurement 查询列）。"""
    (pid, name, description, category, price, exhibitor_id, exhibitor_name,
     exhibition_id, created_at, view_count, favorite_count, search_appearances,
     unit, status, images, booth_id, specs) = row
    ctx = ctx or ProductSideContext()
    details: list[str] = []
    factors: list[FactorScore] = []

    # ---- 1) 行业 industry（30 分）----
    ncat = corpus.prod_cat.get(pid) or normalize_category(category)
    raw_cat = 0.0
    if pcat and ncat:
        raw_cat = category_affinity(ncat, pcat) or 0.0
    if pcat and ncat:
        ind_v = raw_cat
        if proc_exhibition_id and exhibition_id and int(proc_exhibition_id) == int(exhibition_id):
            ind_v = min(1.0, ind_v + SAME_EXHIBITION_BONUS)
        factors.append(FactorScore("industry", ind_v, _industry_label(ind_v, True)))
        if raw_cat >= 1.0:
            details.append(f"品类精确匹配（{category}）")
        elif raw_cat >= 0.6:
            details.append("同大类匹配")
    else:
        factors.append(FactorScore("industry", NEUTRAL_SIMILARITY,
                                   _industry_label(0.0, False)))

    # ---- 2) 产品 product = 0.7 关键词覆盖 + 0.3 展品名精度（30 分）----
    doc_text = corpus.prod_text.get(pid, "")
    doc_tokens = corpus.prod_tokens.get(pid, set())
    kw_v, hits, covered, total = _keyword_stats(core_query, extra_query, doc_text, doc_tokens, idf)
    name_v = _name_coverage(core_query, name)
    prod_v = PRODUCT_KEYWORD_SHARE * kw_v + PRODUCT_PORTFOLIO_SHARE * name_v
    factors.append(FactorScore("product", prod_v,
                               f"产品关键词命中 {covered}/{total} · 展品名精度 {name_v:.2f}"))
    if hits:
        details.append("关键词命中：" + "、".join(hits))

    # ---- 3) 地域 region（15 分）----
    reg_v, reg_label = _region_factor(
        ctx.regions_of_product(exhibitor_id, exhibition_id), ctx.demand_regions,
    )
    factors.append(FactorScore("region", reg_v, reg_label))

    # ---- 4) 预算 budget（15 分）----
    budget_v, budget_label = _budget_factor(_budget_signal(
        budget_min, budget_max,
        *((float(price), float(price)) if price is not None else (None, None)),
    ))
    factors.append(FactorScore("budget", budget_v, budget_label))
    if budget_v >= 1.0:
        details.append("预算区间内")

    # ---- 5) 历史行为 history = 展品自身热度 50% + 需求热度 50%（10 分）----
    product_heat = _log_norm(
        float(view_count or 0) + 3.0 * float(favorite_count or 0),
        HISTORY_FULL_SCALE,
    )
    hist_v = 0.5 * product_heat + 0.5 * ctx.demand_history
    factors.append(FactorScore("history", hist_v, _history_label(hist_v)))
    if product_heat >= 0.8 and (view_count or 0) > 0:
        details.append(f"热门展品（浏览 {int(view_count)}）")

    age = _age_days(created_at, now)
    if age is not None and age <= 5.0:
        details.append(f"{int(age)} 天前上架")

    score, points = _combine_factors(factors, WEIGHTS_PRODUCT)
    reasons = [_explain_factors(factors, score)] + details[:4]
    return float(score), _signals_of(factors), reasons, {"factors": points}


def _product_side_context(db: Session, procurement: Procurement, rows: list[Any]) -> ProductSideContext:
    """整批装配展品方向的地域/热度上下文（展商/展会地域各 1 次批量查询）。"""
    ctx = ProductSideContext(demand_id=procurement.id)
    if procurement.id:
        demand_ctx = _demand_context(db, [procurement.id])
        ctx.demand_regions = demand_ctx.region_of(procurement.id)
        ctx.demand_history = demand_ctx.history_of(procurement.id)
    exhibitor_ids = {r[5] for r in rows if r[5]}
    exhibition_ids = {r[7] for r in rows if r[7]}
    ctx.exhibitor_regions = _exhibitor_regions(db, exhibitor_ids)
    ctx.exhibition_regions = _exhibition_regions(db, exhibition_ids)
    return ctx


def match_products_for_procurement(
    db: Session,
    procurement: Procurement,
    limit: int = 10,
) -> MatchOutcome:
    """采购侧工作流：为一条采购需求推荐匹配展品。"""
    t_start = time.perf_counter()
    now = datetime.now(timezone.utc)
    trace: list[StageTrace] = []

    # S0 需求画像：标题核心词 + 描述细节词（品类走独立行业因子，不混入关键词）
    t0 = time.perf_counter()
    core_query = build_title_query(procurement.title, 3)
    extra_query = build_query([(procurement.description, 1)])
    recall_query = dict(core_query)
    for t, w in extra_query.items():
        recall_query[t] = max(recall_query.get(t, 0), w)
    pcat = normalize_category(procurement.category)
    trace.append(StageTrace(
        "S0 需求画像", (time.perf_counter() - t0) * 1000,
        note=f"核心词 {len(core_query)} + 细节词 {len(extra_query)} / 品类 {procurement.category or '-'}",
    ))

    # S1 多路召回：品类通道 + 关键词倒排通道
    t0 = time.perf_counter()
    corpus = get_corpus(db)
    idf = corpus.idf
    assert idf is not None
    cand: dict[int, str] = {}
    cat_hits = 0
    if pcat:
        for pid, ncat in corpus.prod_cat.items():
            if ncat and ncat == pcat:
                cand[pid] = "cat"
                cat_hits += 1
    top_tokens = [t for t, _ in sorted(recall_query.items(), key=lambda kv: -idf.idf(kv[0]))[:12]]
    kw_weight: Counter = Counter()
    for t, factor in expand_recall_tokens(top_tokens).items():
        w = idf.idf(t) * factor
        for pid in corpus.inverted.get(t, ()):
            kw_weight[pid] += w
    kw_cat = 0
    for pid, _w in kw_weight.most_common(MAX_KW_RECALL):
        if pid not in cand:
            cand[pid] = "kw"
        kw_cat += 1
    trace.append(StageTrace(
        "S1 多路召回", (time.perf_counter() - t0) * 1000,
        count_in=len(corpus.prod_cat), count_out=len(cand),
        note=f"品类通道 {cat_hits} + 关键词通道 {kw_cat}（Top{MAX_KW_RECALL}）→ 去重 {len(cand)}",
    ))

    # S2 过滤（语料仅含已发布展品；此处保护性复核）
    t0 = time.perf_counter()
    rows = (
        db.query(
            Product.id, Product.name, Product.description, Product.category, Product.price,
            Product.exhibitor_id, Product.exhibitor_name, Product.exhibition_id, Product.created_at,
            Product.view_count, Product.favorite_count, Product.search_appearances,
            Product.unit, Product.status, Product.images, Product.booth_id, Product.specs,
        )
        .filter(Product.id.in_(list(cand.keys())), Product.status == "published")
        .all()
    )
    trace.append(StageTrace(
        "S2 候选过滤", (time.perf_counter() - t0) * 1000,
        count_in=len(cand), count_out=len(rows), note="仅保留已发布展品",
    ))

    # S3 打分（五因子，固定权重）
    t0 = time.perf_counter()
    side_ctx = _product_side_context(db, procurement, rows)
    scored: list[tuple[float, Any, list[str], dict[str, int]]] = []
    for row in rows:
        score, _signals, reasons, extra = _score_product_for_procurement(
            row, core_query, extra_query, pcat, procurement.budget_min, procurement.budget_max,
            procurement.exhibition_id, corpus, idf, now, side_ctx,
        )
        s_prod = _signals.get("product") or 0.0
        s_ind = _signals.get("industry") or 0.0
        if s_prod <= 0.0 and s_ind < 0.6:
            continue  # 门控：无关键词命中且行业不匹配 → 不属于"匹配"
        scored.append((score, row, reasons, extra.get("factors", {})))
    trace.append(StageTrace(
        "S3 五因子打分", (time.perf_counter() - t0) * 1000,
        count_in=len(rows), count_out=len(scored),
        note=(f"行业30 + 产品30 + 地域15 + 预算15 + 历史行为10（合计 100）"
              f" · 门控后 {len(scored)}"),
        detail={
            "weights": {k: int(v) for k, v in WEIGHTS_PRODUCT.items()},
            "demand_id": procurement.id,
            "demand_factors": {
                "region": side_ctx.demand_regions,
                "history": round(side_ctx.demand_history, 4),
            },
            "gate": "产品关键词零命中且行业相似度 < 0.6 → 剔除",
        },
    ))

    # S4 排序截断（含冷启动兜底）
    t0 = time.perf_counter()
    scored.sort(key=lambda x: (-x[0], -int(x[1][9] or 0), -int(x[1][0] or 0)))
    top: list[tuple[float, Any, list[str], dict[str, int]]] = scored[:limit]
    if not top:
        fallback = (
            db.query(
                Product.id, Product.name, Product.description, Product.category, Product.price,
                Product.exhibitor_id, Product.exhibitor_name, Product.exhibition_id, Product.created_at,
                Product.view_count, Product.favorite_count, Product.search_appearances,
                Product.unit, Product.status, Product.images, Product.booth_id, Product.specs,
            )
            .filter(Product.status == "published")
            .order_by(Product.id.desc())
            .limit(limit)
            .all()
        )
        top = [(1.0, r, ["最新上架"], {}) for r in fallback]
    items = [
        {
            "id": r[0], "name": r[1], "description": r[2] or "", "category": r[3],
            "price": r[4], "exhibitor_id": r[5], "exhibitor_name": r[6] or "",
            "exhibition_id": r[7], "created_at": r[8].isoformat() if r[8] else None,
            "unit": r[12], "status": r[13], "images": r[14], "booth_id": r[15], "specs": r[16],
            "score": int(round(score)), "match_score": int(round(score)),
            "match_level": _level(score), "reasons": reasons, "match_reasons": reasons,
        }
        for score, r, reasons, _f in top
    ]
    trace.append(StageTrace(
        "S4 排序截断", (time.perf_counter() - t0) * 1000,
        count_in=len(scored), count_out=len(items), note=f"Top-{limit} 阈值门控",
    ))

    # S5 解释生成（本地模板，五因子中文口径）
    t0 = time.perf_counter()
    trace.append(StageTrace(
        "S5 解释生成", (time.perf_counter() - t0) * 1000,
        count_in=len(items), count_out=len(items),
        note="中文五因子解释：总分行 = Σ 分项（行业/产品/地域/预算/历史行为）",
        detail={
            "factor_avg_top": (
                {
                    key: round(sum(int(f.get(key, 0)) for *_x, f in top) / len(top), 2)
                    for key in FACTOR_ORDER
                } if top else {}
            ),
            "samples": [
                {
                    "id": r[0],
                    "match_score": int(round(score)),
                    "factors": f,
                    "explain": reasons[0] if reasons else "",
                }
                for score, r, reasons, f in top[:3]
            ],
        },
    ))

    total_ms = (time.perf_counter() - t_start) * 1000
    return MatchOutcome(
        items=items, trace=trace,
        meta={"recalled": len(cand), "scored": len(scored), "returned": len(items),
              "total_ms": round(total_ms, 2)},
    )


def hot_products_fallback(db: Session, limit: int = 10) -> list[dict[str, Any]]:
    """买家无待匹配需求时的兜底：热度最高的已发布展品（浏览/收藏排序）。"""
    rows = (
        db.query(Product)
        .filter(Product.status == "published")
        .order_by((Product.view_count + Product.favorite_count * 3).desc(), Product.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id, "name": p.name, "category": p.category,
            "exhibitor_name": p.exhibitor_name or "",
            "description": p.description or "",
            "score": 1, "match_score": 1, "match_level": "low",
            "reasons": ["热门展品"], "match_reasons": ["热门展品"],
        }
        for p in rows
    ]


# ============================================================
# 观测：GET /api/matching/cache-stats（公开只读）
# ============================================================
#
# 只读进程内计数器，不查库、不写库；用于确认撮合是否走了缓存、构建耗时多少。
# 返回 {hits, misses, build_ms, size}，另附 corpus/profile 分项（便于定位问题）。

router = APIRouter(tags=["匹配工作流"])


@router.get("/matching/cache-stats", summary="匹配缓存观测（hits/misses/build_ms/size）")
def matching_cache_stats() -> dict[str, Any]:
    """进程级缓存观测快照：命中/未命中次数、累计构建耗时、当前条目数。"""
    return cache_stats()

