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
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user
from app.models.base import get_db
from app.models.user import User
from app.modules.matching.workflow import (
    hot_products_fallback,
    latest_pending_procurement,
    match_procurements_for_exhibitor,
    match_products_for_procurement,
    score_procurements_for_exhibitor,
)

router = APIRouter(prefix="/recommendations", tags=["智能推荐"])


@router.get("/for-exhibitor")
def for_exhibitor(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
):
    """给展商推荐匹配的采购需求（工作流：画像→召回→打分→排序→解释）"""
    outcome = match_procurements_for_exhibitor(db, current_user, limit=limit)
    return {
        "success": True, "code": "OK",
        "data": outcome.items,
        "pipeline": outcome.as_payload(),
        "message": f"为你找到{len(outcome.items)}条匹配的采购需求",
    }


@router.get("/for-buyer")
def for_buyer(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
):
    """给买家推荐匹配的展品（以最新一条待匹配采购需求为查询）"""
    procurement = latest_pending_procurement(db, current_user.id)
    if not procurement:
        data = hot_products_fallback(db, limit)
        return {
            "success": True, "code": "OK",
            "data": data,
            "pipeline": {"engine": "match-workflow-local", "version": "1.0",
                         "mode": "fallback-hot", "returned": len(data), "stages": []},
            "message": "请先发布采购需求获取精准匹配，以下是热门展品",
        }

    outcome = match_products_for_procurement(db, procurement, limit=limit)
    return {
        "success": True, "code": "OK",
        "data": outcome.items,
        "pipeline": outcome.as_payload(),
        "message": f"根据'{procurement.category or '需求'}'为你匹配{len(outcome.items)}个展品",
    }


@router.get("/score-procurements")
def score_procurements(
    ids: str = Query(..., description="逗号分隔的采购需求 ID，最多 100 个"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """对指定采购需求实时打分（列表页「匹配度」徽章/排序用）"""
    id_list: list[int] = []
    for part in ids.split(","):
        part = part.strip()
        if part.isdigit():
            id_list.append(int(part))
        if len(id_list) >= 100:
            break
    scores, meta = score_procurements_for_exhibitor(db, current_user, id_list)
    return {
        "success": True, "code": "OK",
        "data": scores,
        "pipeline": meta,
        "message": "评分完成",
    }
