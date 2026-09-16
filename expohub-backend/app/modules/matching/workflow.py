"""
智能匹配工作流 (Match Workflow)

把「智能推荐」从散落的规则函数重构为一条**显式的多阶段工作流**，每个阶段
职责单一、可观测（耗时/候选数/说明写入 trace）、可降级（全链路零云依赖）：

    S0 画像装配  ── 展商画像（行业领域+展品品类+关键词+价格带+展位热度）
    │               或采购需求画像（标题/描述/品类/预算/时效）
    S1 多路召回  ── 品类通道 + 关键词倒排通道（IDF 加权），合并去重
    S2 候选过滤  ── 状态/自单/已应标剔除
    S3 多信号打分── 品类相似度 · 关键词覆盖 · 预算吻合 · 新鲜度 · 展品/热度信号
    S4 排序截断  ── 加权总分降序 + 阈值门控 + Top-K
    S5 解释生成  ── 本地模板生成逐信号推荐理由（无 LLM）

LLM 仅作为可选的「AI 解读」增强（由 /api/ai 承担），失败/超时自动降级到
S5 的本地解释，不影响主链路。

设计约束：
- 纯本地：无网络调用、无新增数据库表（jieba 为可选依赖，缺失自动降级）
- 语料缓存：产品分词/IDF/倒排索引按「数据指纹」进程内缓存，变更自动重建
- 参数集中：权重/阈值/半衰期集中在文件头部常量，便于调参与演示讲解
"""
from __future__ import annotations

import math
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.micro_booth import MicroBooth
from app.models.procurement import Procurement
from app.models.procurement_match import ProcurementMatch
from app.models.product import Product
from app.models.user import User
from app.modules.matching.textkit import (
    IdfModel,
    build_query,
    build_title_query,
    category_affinity,
    expand_recall_tokens,
    keyword_coverage_tiered,
    normalize_category,
    tokenize,
)

# ============================================================
# 工作流参数（唯一调参入口）
# ============================================================

# 展商 ← 采购需求 方向：各信号权重（信号不可用时按可用权重归一化）
WEIGHTS_EXHIBITOR: dict[str, float] = {
    "category": 0.32,   # 品类相似度（归一化后精确/同父组）
    "keyword": 0.38,    # 关键词 IDF 加权覆盖率（含同义词回退）
    "portfolio": 0.10,  # 展商展品池命中数（有几个展品与该需求相关）
    "budget": 0.10,     # 预算区间与展品价格带吻合度
    "freshness": 0.10,  # 需求新鲜度（指数衰减）
}

# 采购需求 ← 展品 方向
WEIGHTS_PRODUCT: dict[str, float] = {
    "category": 0.32,
    "keyword": 0.40,    # 展品文本关键词覆盖
    "budget": 0.10,     # 预算与展品价格吻合度
    "freshness": 0.08,  # 展品上架新鲜度
    "quality": 0.10,    # 展品热度（浏览/收藏/曝光）
}

FRESH_HALF_LIFE_DAYS = 14.0   # 新鲜度指数衰减半衰期（天）
SAME_EXHIBITION_BONUS = 0.20  # 同一展会上下文对品类信号的加成
NOTIFY_MIN_SCORE = 55         # 发布采购时给展商推送通知的最低匹配度
TEXT_SNIPPET = 80             # 展品描述参与分词的截断长度（控制缓存构建成本）
MAX_KW_RECALL = 400           # 关键词通道召回上限（保护延迟）


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ms": round(self.ms, 2),
            "in": self.count_in,
            "out": self.count_out,
            "note": self.note,
        }


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


# ============================================================
# 语料缓存：产品分词 / IDF / 倒排索引
# ============================================================

class _Corpus:
    def __init__(self, fingerprint: tuple, built_at: float):
        self.fingerprint = fingerprint
        self.built_at = built_at
        self.prod_tokens: dict[int, set[str]] = {}
        self.prod_text: dict[int, str] = {}
        self.prod_cat: dict[int, str] = {}
        self.idf: Optional[IdfModel] = None
        self.inverted: dict[str, set[int]] = {}

    def freshness(self) -> float:
        return time.time() - self.built_at


_corpus_lock = threading.Lock()
_CORPUS: Optional[_Corpus] = None
_CORPUS_TTL = 600.0  # 秒；指纹未变但超过 TTL 也重建（防状态字段漏检）


def _corpus_fingerprint(db: Session) -> tuple:
    row = (
        db.query(
            func.count(Product.id),
            func.max(Product.id),
            func.max(Product.updated_at),
        )
        .filter(Product.status == "published")
        .one()
    )
    return (int(row[0] or 0), int(row[1] or 0), str(row[2] or ""))


def _build_corpus(db: Session, fingerprint: tuple) -> _Corpus:
    corpus = _Corpus(fingerprint, time.time())
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
    """获取产品语料（分词/IDF/倒排），按数据指纹进程内缓存，变更自动重建。"""
    global _CORPUS
    fp = _corpus_fingerprint(db)
    cur = _CORPUS
    if cur is not None and cur.fingerprint == fp and cur.freshness() < _CORPUS_TTL:
        return cur
    with _corpus_lock:
        cur = _CORPUS
        if cur is not None and cur.fingerprint == fp and cur.freshness() < _CORPUS_TTL:
            return cur
        _CORPUS = _build_corpus(db, fp)
        return _CORPUS


def invalidate_corpus() -> None:
    """显式失效语料缓存（测试/数据批量导入后调用）。"""
    global _CORPUS
    _CORPUS = None


# ============================================================
# 工具
# ============================================================

def _age_days(dt: Optional[datetime], now: datetime) -> Optional[float]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def _freshness(age: Optional[float]) -> Optional[float]:
    if age is None:
        return None
    return math.exp(-age / FRESH_HALF_LIFE_DAYS)


def _weighted_score(signals: dict[str, Optional[float]], weights: dict[str, float]) -> float:
    """按可用信号加权归一化 → 0~100 分。"""
    avail = [(weights.get(k, 0.0), v) for k, v in signals.items() if v is not None]
    total_w = sum(w for w, _ in avail if w > 0)
    if total_w <= 0:
        return 0.0
    return round(100.0 * sum(w * v for w, v in avail if w > 0) / total_w, 1)


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
    if score >= 75:
        return "high"
    if score >= NOTIFY_MIN_SCORE:
        return "medium"
    return "low"


# ============================================================
# S0 画像装配
# ============================================================

def build_exhibitor_profile(db: Session, user: User) -> ExhibitorProfile:
    """展商画像：行业领域 + 展品品类/关键词/价格带 + 微展位信息。"""
    profile = ExhibitorProfile(user_id=user.id)
    if user.industry_domain:
        nc = normalize_category(user.industry_domain)
        if nc:
            profile.cats.add(nc)

    corpus = get_corpus(db)
    prods = (
        db.query(Product.id, Product.category, Product.price, Product.exhibition_id)
        .filter(Product.exhibitor_id == user.id, Product.status == "published")
        .all()
    )
    texts: list[str] = []
    for pid, cat, price, exh_id in prods:
        nc = normalize_category(cat)
        if nc:
            profile.cats.add(nc)
        toks = corpus.prod_tokens.get(pid)
        if toks is None:  # 语料指纹竞态兜底：现场分词
            toks = set(tokenize(f"{cat or ''}"))
        for t in toks:
            profile.tokens[t] += 2
        profile.product_token_sets.append(toks)
        if price is not None:
            price = float(price)
            profile.price_min = price if profile.price_min is None else min(profile.price_min, price)
            profile.price_max = price if profile.price_max is None else max(profile.price_max, price)
        if exh_id:
            profile.exhibition_ids.add(int(exh_id))
        texts.append(corpus.prod_text.get(pid, ""))

    booths = (
        db.query(MicroBooth.industry_domain, MicroBooth.name, MicroBooth.description,
                 MicroBooth.view_count, MicroBooth.favorite_count)
        .filter(MicroBooth.exhibitor_id == user.id)
        .all()
    )
    for ind, bname, bdesc, views, favs in booths:
        if ind:
            nc = normalize_category(ind)
            if nc:
                profile.cats.add(nc)
        for t in tokenize(f"{bname or ''} {bdesc or ''}"):
            profile.tokens[t] += 1
        pop = math.log1p(float(views or 0) + 3.0 * float(favs or 0))
        profile.booth_score = max(profile.booth_score, min(1.0, pop / math.log1p(500.0)))

    profile.text = " ".join(texts)
    profile.token_set = set(profile.tokens)
    profile.cats.discard("")
    return profile


# ============================================================
# 方向一：展商 ← 采购需求
# ============================================================

def _score_procurement_for_profile(
    p: Procurement,
    profile: ExhibitorProfile,
    idf: IdfModel,
    now: datetime,
) -> tuple[float, dict[str, Optional[float]], list[str], dict[str, Any]]:
    """对单条采购需求打分（S3），返回 (总分, 信号明细, 理由, 附加信息)。"""
    reasons: list[str] = []
    signals: dict[str, Optional[float]] = {}

    # --- 品类信号 ---
    pcat = normalize_category(p.category)
    raw_cat = 0.0
    if pcat:
        for c in profile.cats:
            aff = category_affinity(c, pcat)
            if aff is not None:
                raw_cat = max(raw_cat, aff)
    if pcat:
        cat_v = raw_cat
        if p.exhibition_id and int(p.exhibition_id) in profile.exhibition_ids:
            cat_v = min(1.0, cat_v + SAME_EXHIBITION_BONUS)
        signals["category"] = cat_v
        if raw_cat >= 1.0:
            reasons.append(f"品类精确匹配：{p.category}")
        elif raw_cat >= 0.6:
            reasons.append(f"同大类匹配（{pcat}）")
    else:
        signals["category"] = None

    # --- 关键词信号（两层覆盖：标题核心词 70% + 全量含描述 30%，IDF 加权 + 同义词回退）---
    core_query = build_title_query(p.title, 3)
    extra_query = build_query([(p.description, 1)])
    kw_v, hits = keyword_coverage_tiered(
        core_query, extra_query, profile.text, profile.token_set, idf,
    )
    signals["keyword"] = kw_v
    if hits:
        reasons.append("关键词命中：" + "、".join(hits))

    # --- 展品池信号：展商有几个展品与该需求相关 ---
    probe_tokens = set(hits) or {
        t for t, _ in sorted(core_query.items(), key=lambda kv: -idf.idf(kv[0]))[:5]
    }
    related_products = sum(1 for toks in profile.product_token_sets if toks & probe_tokens)
    signals["portfolio"] = min(1.0, related_products / 3.0) if profile.product_token_sets else None

    # --- 门控：关键词零命中且无相关展品 → 判为不匹配（防泛品类蹭分）---
    if not hits and related_products == 0:
        return 0.0, signals, [], {"related_products": 0}
    if related_products >= 2:
        reasons.append(f"与你 {related_products} 个展品相关")

    # --- 预算信号 ---
    budget_v = _budget_signal(p.budget_min, p.budget_max, profile.price_min, profile.price_max)
    signals["budget"] = budget_v
    if budget_v == 1.0:
        reasons.append("预算区间与展品价格带吻合")

    # --- 新鲜度信号 ---
    age = _age_days(p.created_at, now)
    signals["freshness"] = _freshness(age)
    if age is not None and age <= 5.0:
        reasons.append("新发布需求" if age <= 1.5 else f"{int(age)} 天前发布")

    score = _weighted_score(signals, WEIGHTS_EXHIBITOR)
    return score, signals, reasons[:4], {"related_products": related_products}


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
        note=f"品类 {len(profile.cats)} / 关键词 {len(profile.tokens)} / 展品 {len(profile.product_token_sets)}",
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

    # S3 打分
    t0 = time.perf_counter()
    scored: list[tuple[float, int, Procurement, list[str]]] = []
    for p in filtered:
        score, _signals, reasons, extra = _score_procurement_for_profile(p, profile, idf, now)
        if score <= 0:
            continue
        scored.append((score, int(extra.get("related_products", 0)), p, reasons))
    trace.append(StageTrace(
        "S3 多信号打分", (time.perf_counter() - t0) * 1000,
        count_in=len(filtered), count_out=len(scored),
        note="品类/关键词/展品池/预算/新鲜度 加权",
    ))

    # S4 排序截断（含冷启动兜底）
    t0 = time.perf_counter()
    scored.sort(key=lambda x: (-x[0], -x[1], -(x[2].id or 0)))
    top: list[tuple[float, int, Procurement, list[str]]] = scored[:limit]
    if not top:
        top = [(1.0, 0, p, ["最新发布"]) for p in candidates[:limit]]
    items = [
        {
            "id": p.id, "title": p.title, "description": p.description,
            "category": p.category, "budget_min": p.budget_min, "budget_max": p.budget_max,
            "status": p.status, "purchaser_name": p.purchaser_name,
            "score": int(round(score)), "match_score": int(round(score)),
            "match_level": _level(score), "reasons": reasons,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for score, _rel, p, reasons in top
    ]
    trace.append(StageTrace(
        "S4 排序截断", (time.perf_counter() - t0) * 1000,
        count_in=len(scored), count_out=len(items), note=f"Top-{limit} 阈值门控",
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
    hits: list[dict[str, Any]] = []
    for user in exhibitors:
        if user.id == procurement.purchaser_id:
            continue
        try:
            profile = build_exhibitor_profile(db, user)
            if not profile.cats and not profile.tokens:
                continue
            score, _signals, reasons, _extra = _score_procurement_for_profile(
                procurement, profile, corpus.idf, now,
            )
            if score >= NOTIFY_MIN_SCORE:
                hits.append({"user_id": user.id, "score": score,
                             "reason": reasons[0] if reasons else "综合匹配"})
        except Exception:  # 单个展商画像失败不影响整体通知
            continue
    hits.sort(key=lambda x: -x["score"])
    return hits[:5]


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
    profile = build_exhibitor_profile(db, user)
    corpus = get_corpus(db)
    idf = corpus.idf
    assert idf is not None
    procs = (
        db.query(Procurement).filter(Procurement.id.in_(procurement_ids)).all()
        if procurement_ids else []
    )
    result: dict[int, dict[str, Any]] = {}
    for p in procs:
        score, _signals, reasons, _extra = _score_procurement_for_profile(p, profile, idf, now)
        result[p.id] = {
            "match_score": int(round(score)),
            "match_level": _level(score),
            "reasons": reasons,
        }
    meta = {
        "engine": "match-workflow-local", "version": "1.0",
        "scored": len(result), "total_ms": round((time.perf_counter() - t_start) * 1000, 2),
        "stages": [],
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
) -> tuple[float, dict[str, Optional[float]], list[str], dict[str, Any]]:
    """对单个展品打分（S3）。row 为展品字段行（见 match_products_for_procurement 查询列）。"""
    (pid, name, description, category, price, exhibitor_id, exhibitor_name,
     exhibition_id, created_at, view_count, favorite_count, search_appearances,
     unit, status, images, booth_id, specs) = row
    reasons: list[str] = []
    signals: dict[str, Optional[float]] = {}

    # --- 品类信号 ---
    ncat = corpus.prod_cat.get(pid) or normalize_category(category)
    raw_cat = 0.0
    if pcat and ncat:
        raw_cat = category_affinity(ncat, pcat) or 0.0
    if pcat and ncat:
        cat_v = raw_cat
        if proc_exhibition_id and exhibition_id and int(proc_exhibition_id) == int(exhibition_id):
            cat_v = min(1.0, cat_v + SAME_EXHIBITION_BONUS)
        signals["category"] = cat_v
        if raw_cat >= 1.0:
            reasons.append(f"品类精确匹配（{category}）")
        elif raw_cat >= 0.6:
            reasons.append("同大类匹配")
    else:
        signals["category"] = None

    # --- 关键词信号（两层覆盖：标题核心词 70% + 全量含描述 30%）---
    doc_text = corpus.prod_text.get(pid, "")
    doc_tokens = corpus.prod_tokens.get(pid, set())
    kw_v, hits = keyword_coverage_tiered(core_query, extra_query, doc_text, doc_tokens, idf)
    signals["keyword"] = kw_v
    if hits:
        reasons.append("关键词命中：" + "、".join(hits))

    # --- 预算/价格信号 ---
    budget_v = _budget_signal(budget_min, budget_max, *(
        (float(price), float(price)) if price is not None else (None, None)
    ))
    signals["budget"] = budget_v
    if budget_v == 1.0:
        reasons.append("预算区间内")

    # --- 新鲜度 ---
    age = _age_days(created_at, now)
    signals["freshness"] = _freshness(age)

    # --- 热度信号 ---
    heat = math.log1p(float(view_count or 0) + 3.0 * float(favorite_count or 0)
                      + 0.5 * float(search_appearances or 0))
    quality_v = min(1.0, heat / math.log1p(300.0))
    signals["quality"] = quality_v
    if quality_v >= 0.8 and (view_count or 0) > 0:
        reasons.append(f"热门展品（浏览 {int(view_count)}）")

    score = _weighted_score(signals, WEIGHTS_PRODUCT)
    return score, signals, reasons[:4], {}


def match_products_for_procurement(
    db: Session,
    procurement: Procurement,
    limit: int = 10,
) -> MatchOutcome:
    """采购侧工作流：为一条采购需求推荐匹配展品。"""
    t_start = time.perf_counter()
    now = datetime.now(timezone.utc)
    trace: list[StageTrace] = []

    # S0 需求画像：标题核心词 + 描述细节词（品类走独立品类信号，不混入关键词）
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

    # S3 打分
    t0 = time.perf_counter()
    scored: list[tuple[float, Any, list[str]]] = []
    for row in rows:
        score, _signals, reasons, _extra = _score_product_for_procurement(
            row, core_query, extra_query, pcat, procurement.budget_min, procurement.budget_max,
            procurement.exhibition_id, corpus, idf, now,
        )
        s_kw = _signals.get("keyword") or 0.0
        s_cat = _signals.get("category") or 0.0
        if s_kw <= 0.0 and s_cat < 0.6:
            continue  # 门控：无关键词命中且品类不匹配 → 不属于"匹配"
        scored.append((score, row, reasons))
    trace.append(StageTrace(
        "S3 多信号打分", (time.perf_counter() - t0) * 1000,
        count_in=len(rows), count_out=len(scored),
        note=f"品类/关键词/预算/新鲜度/热度 加权 · 门控后 {len(scored)}",
    ))

    # S4 排序截断（含冷启动兜底）
    t0 = time.perf_counter()
    scored.sort(key=lambda x: (-x[0], -int(x[1][9] or 0), -int(x[1][0] or 0)))
    top = scored[:limit]
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
        top = [(1.0, r, ["最新上架"]) for r in fallback]
    items = [
        {
            "id": r[0], "name": r[1], "description": r[2] or "", "category": r[3],
            "price": r[4], "exhibitor_id": r[5], "exhibitor_name": r[6] or "",
            "exhibition_id": r[7], "created_at": r[8].isoformat() if r[8] else None,
            "unit": r[12], "status": r[13], "images": r[14], "booth_id": r[15], "specs": r[16],
            "score": int(round(score)), "match_score": int(round(score)),
            "match_level": _level(score), "reasons": reasons, "match_reasons": reasons,
        }
        for score, r, reasons in top
    ]
    trace.append(StageTrace(
        "S4 排序截断", (time.perf_counter() - t0) * 1000,
        count_in=len(scored), count_out=len(items), note=f"Top-{limit} 阈值门控",
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
