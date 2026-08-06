"""
V2.3: 智能匹配推荐
关键词+品类双重匹配，直接匹配10000+产品池
"""

import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.base import get_db
from app.models.user import User
from app.models.procurement import Procurement
from app.models.micro_booth import MicroBooth
from app.models.product import Product
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/recommendations", tags=["智能推荐"])


def _keyword_score(query: str, text: str) -> int:
    """简单关键词匹配：query中每个字在text中出现就加分"""
    if not query or not text:
        return 0
    q_chars = set(query.replace(" ", ""))
    t_chars = set(text.replace(" ", ""))
    overlap = len(q_chars & t_chars)
    return min(overlap * 3, 30)


def _category_fuzzy_match(cat1: str, cat2: str) -> int:
    """模糊品类匹配"""
    if not cat1 or not cat2:
        return 0
    if cat1 == cat2:
        return 50
    # 检查是否在同一父组
    from app.models.category import match_category_score
    return match_category_score(cat1, cat2)


@router.get("/for-exhibitor")
def for_exhibitor(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
):
    """给展商推荐匹配的采购需求"""
    domain = current_user.industry_domain or ""

    # 也查展商的产品品类作为额外匹配条件
    product_cats = set()
    if current_user.role == "exhibitor":
        cats = db.query(Product.category).filter(
            Product.exhibitor_id == current_user.id, Product.status == "published"
        ).distinct().limit(20).all()
        product_cats = {c[0] for c in cats if c[0]}

    all_cats = {domain} | product_cats
    all_cats.discard("")

    procurements = db.query(Procurement).filter(
        Procurement.status == "pending"
    ).order_by(Procurement.created_at.desc()).limit(200).all()

    scored = []
    for p in procurements:
        score = 0
        reasons = []

        # 品类匹配
        for cat in all_cats:
            s = _category_fuzzy_match(cat, p.category or "")
            if s >= 50:
                score += 50
                reasons.append(f"品类精确匹配：{p.category}")
                break
            elif s >= 30:
                score += 30
                reasons.append(f"同行业大类：{p.category}")
                break
            elif s >= 10:
                score += 10

        # 关键词匹配（标题中包含品类词）
        for cat in all_cats:
            ks = _keyword_score(cat, p.title or "")
            if ks > 0:
                score += ks
                reasons.append(f"关键词匹配")

        # 预算加分
        if p.budget_max:
            score += 5

        # 只要有点关联就返回（降低门槛）
        if score >= 5:
            scored.append({
                "id": p.id, "title": p.title, "description": p.description,
                "category": p.category, "budget_min": p.budget_min,
                "budget_max": p.budget_max, "status": p.status,
                "purchaser_name": p.purchaser_name,
                "score": score, "reasons": reasons[:3],
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    if not scored:
        # 兜底：返回最新采购需求
        latest = procurements[:limit]
        scored = [{
            "id": p.id, "title": p.title, "description": p.description,
            "category": p.category, "status": p.status,
            "purchaser_name": p.purchaser_name,
            "score": 1, "reasons": ["最新发布"],
            "created_at": p.created_at.isoformat() if p.created_at else None,
        } for p in latest]

    return {
        "success": True, "code": "OK",
        "data": scored[:limit],
        "message": f"为你找到{len(scored[:limit])}条匹配的采购需求",
    }


@router.get("/for-buyer")
def for_buyer(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
):
    """给买家推荐匹配的展商和产品"""
    procurement = db.query(Procurement).filter(
        Procurement.purchaser_id == current_user.id,
        Procurement.status == "pending",
    ).order_by(Procurement.created_at.desc()).first()

    if not procurement:
        # 兜底：返回热门产品
        hot = db.query(Product).filter(
            Product.status == "published"
        ).order_by(Product.created_at.desc()).limit(limit).all()
        return {
            "success": True, "code": "OK",
            "data": [{
                "id": p.id, "name": p.name, "category": p.category,
                "exhibitor_name": p.exhibitor_name or "",
                "description": p.description or "",
                "score": 1, "reasons": ["热门展品"],
            } for p in hot],
            "message": "请先发布采购需求获取精准匹配，以下是热门展品",
        }

    cat = procurement.category or ""
    keywords = procurement.title or ""

    # 从10000产品中匹配
    products = db.query(Product).filter(
        Product.status == "published"
    ).order_by(Product.created_at.desc()).limit(500).all()

    scored = []
    for p in products:
        score = 0
        reasons = []

        # 品类匹配
        s = _category_fuzzy_match(cat, p.category or "")
        if s >= 50:
            score += 50
            reasons.append(f"品类精确匹配")
        elif s >= 30:
            score += 30
            reasons.append(f"同行业大类")

        # 关键词匹配（标题+描述）
        ks = _keyword_score(keywords, (p.name or "") + (p.description or ""))
        if ks > 0:
            score += ks
            if ks >= 15:
                reasons.append("关键词高度匹配")

        if score >= 5:
            scored.append({
                "id": p.id, "name": p.name, "category": p.category,
                "description": p.description or "",
                "exhibitor_name": p.exhibitor_name or "",
                "exhibitor_id": p.exhibitor_id,
                "score": score, "reasons": reasons,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    if not scored:
        # 兜底：全品类热门
        hot = db.query(Product).filter(
            Product.status == "published"
        ).order_by(Product.created_at.desc()).limit(limit).all()
        scored = [{
            "id": p.id, "name": p.name, "category": p.category,
            "exhibitor_name": p.exhibitor_name or "",
            "description": p.description or "",
            "score": 1, "reasons": ["热门展品"],
        } for p in hot]

    return {
        "success": True, "code": "OK",
        "data": scored[:limit],
        "message": f"根据'{cat}'为你匹配{len(scored[:limit])}个展品",
    }
