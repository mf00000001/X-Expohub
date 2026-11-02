"""
V3.5: 智能推荐（匹配工作流接入版）

智能推荐不再是散落的规则函数，而是统一走 `app.modules.matching.workflow`
的多阶段匹配工作流（S0 画像装配 → S1 多路召回 → S2 过滤 → S3 多信号打分 →
S4 排序截断 → S5 解释生成），全链路本地运行、毫秒级、零云依赖。

端点：
- GET /recommendations/for-exhibitor           展商 ← 采购需求（Top-K 推荐）
- GET /recommendations/for-buyer               买家 ← 展品（最新待匹配需求驱动）
- GET /recommendations/score-procurements      对指定采购需求实时打分（列表页匹配度徽章）

响应约定（兼容旧契约）：
- data 仍为列表；条目保留旧字段（score/reasons/...），新增 match_score(0-100)、
  match_level(high/medium/low)、match_reasons（展品侧）
- 顶层新增 pipeline 字段：工作流阶段 trace（名称/耗时/进出数量/说明），
  供前端展示「本地匹配工作流」运行摘要
- 顶层新增 personalized 字段（true/false）：本次结果是否使用了个性化画像

2026-10-19 合规降级（PIPL 第 24 条 / 算法推荐规定第 17 条）：
用户可在设置页关闭个性化推荐（users.personalized_recommend=false）。关闭后本文件
三个端点不再装配画像、不做匹配打分，改为按「最新内容」排序返回；此时
pipeline.engine 标记为 non-personalized-recency，personalized=false，
其余响应字段名与旧契约完全一致（前端仍读 data 列表与 match_score）。
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user
from app.models.base import get_db
from app.models.procurement import Procurement
from app.models.product import Product
from app.models.user import User
from app.modules.matching.workflow import (
    hot_products_fallback,
    latest_pending_procurement,
    match_procurements_for_exhibitor,
    match_products_for_procurement,
    score_procurements_for_exhibitor,
)

router = APIRouter(prefix="/recommendations", tags=["智能推荐"])


# ============================================================
# 非个性化（按最新内容）降级：开关、文案与取数
# ============================================================

# 关闭个性化推荐后统一使用的解释文案与引擎标识
NON_PERSONALIZED_NOTE = "已关闭个性化推荐，按最新内容展示"
NON_PERSONALIZED_ENGINE = "non-personalized-recency"


def _is_personalized(user: User) -> bool:
    """本次请求是否需要个性化推荐（默认开启；用户显式关闭后为 False）"""
    return bool(getattr(user, "personalized_recommend", True))


def _non_personalized_pipeline(returned: int, mode: str = "recency") -> dict[str, Any]:
    """关闭个性化推荐时的 pipeline 摘要（字段名与工作流 payload 对齐）"""
    return {
        "engine": NON_PERSONALIZED_ENGINE,
        "version": "1.0",
        "mode": mode,
        "returned": returned,
        "stages": [],
    }


def _latest_pending_procurements(db: Session, limit: int) -> list[dict[str, Any]]:
    """最新待匹配采购需求（created_at desc）：展商侧的非个性化列表"""
    rows = (
        db.query(Procurement)
        .filter(Procurement.status == "pending")
        .order_by(Procurement.created_at.desc(), Procurement.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id, "title": p.title, "description": p.description,
            "category": p.category, "budget_min": p.budget_min, "budget_max": p.budget_max,
            "status": p.status, "purchaser_name": p.purchaser_name,
            "score": 0, "match_score": 0, "match_level": "normalized",
            "reasons": [NON_PERSONALIZED_NOTE],
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ]


def _latest_published_products(db: Session, limit: int) -> list[dict[str, Any]]:
    """最新已发布展品（created_at desc）：买家侧的非个性化列表"""
    rows = (
        db.query(Product)
        .filter(Product.status == "published")
        .order_by(Product.created_at.desc(), Product.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id, "name": p.name, "description": p.description or "",
            "category": p.category, "exhibitor_id": p.exhibitor_id,
            "exhibitor_name": p.exhibitor_name or "",
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "score": 0, "match_score": 0, "match_level": "normalized",
            "reasons": [NON_PERSONALIZED_NOTE], "match_reasons": [NON_PERSONALIZED_NOTE],
        }
        for p in rows
    ]


def _non_personalized_scores(procurement_ids: list[int]) -> dict[int, dict[str, Any]]:
    """等长的占位评分（不读画像）：匹配度统一置 0，前端仅在 >0 时展示徽章"""
    return {
        pid: {
            "match_score": 0,
            "match_level": "normalized",
            "reasons": [NON_PERSONALIZED_NOTE],
        }
        for pid in procurement_ids
    }


@router.get("/for-exhibitor")
def for_exhibitor(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
):
    """给展商推荐匹配的采购需求（工作流：画像→召回→打分→排序→解释）

    关闭个性化推荐时：跳过画像装配与打分，直接按发布时间倒序返回最新待匹配需求。
    """
    if not _is_personalized(current_user):
        items = _latest_pending_procurements(db, limit)
        return {
            "success": True, "code": "OK",
            "data": items,
            "personalized": False,
            "pipeline": _non_personalized_pipeline(len(items)),
            "message": f"已关闭个性化推荐，按最新发布为你展示{len(items)}条采购需求",
        }

    outcome = match_procurements_for_exhibitor(db, current_user, limit=limit)
    return {
        "success": True, "code": "OK",
        "data": outcome.items,
        "personalized": True,
        "pipeline": outcome.as_payload(),
        "message": f"为你找到{len(outcome.items)}条匹配的采购需求",
    }


@router.get("/for-buyer")
def for_buyer(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
):
    """给买家推荐匹配的展品（以最新一条待匹配采购需求为查询）

    关闭个性化推荐时：跳过需求驱动与画像匹配，按上架时间倒序返回最新展品。
    """
    if not _is_personalized(current_user):
        items = _latest_published_products(db, limit)
        return {
            "success": True, "code": "OK",
            "data": items,
            "personalized": False,
            "pipeline": _non_personalized_pipeline(len(items)),
            "message": f"已关闭个性化推荐，按最新上架为你展示{len(items)}个展品",
        }

    procurement = latest_pending_procurement(db, current_user.id)
    if not procurement:
        data = hot_products_fallback(db, limit)
        return {
            "success": True, "code": "OK",
            "data": data,
            "personalized": True,
            "pipeline": {"engine": "match-workflow-local", "version": "1.0",
                         "mode": "fallback-hot", "returned": len(data), "stages": []},
            "message": "请先发布采购需求获取精准匹配，以下是热门展品",
        }

    outcome = match_products_for_procurement(db, procurement, limit=limit)
    return {
        "success": True, "code": "OK",
        "data": outcome.items,
        "personalized": True,
        "pipeline": outcome.as_payload(),
        "message": f"根据'{procurement.category or '需求'}'为你匹配{len(outcome.items)}个展品",
    }


@router.get("/score-procurements")
def score_procurements(
    ids: str = Query(..., description="逗号分隔的采购需求 ID，最多 100 个"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """对指定采购需求实时打分（列表页「匹配度」徽章/排序用）

    关闭个性化推荐时：不装配画像，按请求顺序返回等长的占位评分（match_score=0）。
    """
    id_list: list[int] = []
    for part in ids.split(","):
        part = part.strip()
        if part.isdigit():
            id_list.append(int(part))
        if len(id_list) >= 100:
            break

    if not _is_personalized(current_user):
        scores = _non_personalized_scores(id_list)
        return {
            "success": True, "code": "OK",
            "data": scores,
            "personalized": False,
            "pipeline": _non_personalized_pipeline(len(scores), mode="skip-scoring"),
            "message": NON_PERSONALIZED_NOTE,
        }

    scores, meta = score_procurements_for_exhibitor(db, current_user, id_list)
    return {
        "success": True, "code": "OK",
        "data": scores,
        "personalized": True,
        "pipeline": meta,
        "message": "评分完成",
    }
