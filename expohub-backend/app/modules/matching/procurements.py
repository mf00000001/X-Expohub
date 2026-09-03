"""
采购需求路由（Procurements）

端点：
- GET    /procurements                   采购需求列表
- GET    /procurements/my                我的采购需求
- GET    /procurements/:id               采购需求详情
- POST   /procurements                   创建采购需求
- PUT    /procurements/:id               更新采购需求
- DELETE /procurements/:id               删除采购需求
- POST   /procurements/:id/cancel        取消采购需求
- GET    /procurements/:id/matches       获取匹配列表
- POST   /procurements/:id/matches       创建匹配（展商投标）
- POST   /procurements/:id/matches/:mid/accept  接受匹配
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.base import get_db
from app.models.user import User
from app.models.procurement import Procurement
from app.models.procurement_match import ProcurementMatch
from app.models.category import match_category_score, EXHIBITION_CATEGORIES
from app.models.product import Product
from app.core.deps import get_current_active_user
from app.core.exceptions import NotFound, Forbidden, BadRequest

router = APIRouter(prefix="/procurements", tags=["采购需求"])


# ============================================================
# Pydantic Schemas
# ============================================================

class ProcurementCreate(BaseModel):
    """创建采购需求请求"""
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    deadline: Optional[str] = None


class ProcurementUpdate(BaseModel):
    """更新采购需求请求（所有字段可选）"""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    deadline: Optional[str] = None
    status: Optional[str] = None


class MatchCreate(BaseModel):
    """创建匹配请求（展商投标）"""
    message: Optional[str] = None
    quoted_price: Optional[float] = None
    product_id: Optional[int] = None


# ============================================================
# 工具函数
# ============================================================

def _procurement_to_dict(p: Procurement, match_count: int = 0) -> dict:
    """将 Procurement 模型转为前端响应格式（匹配 ProcurementItem 接口）"""
    return {
        "id": p.id,
        "visitor_id": p.purchaser_id,
        "visitor_username": p.purchaser_name,
        "title": p.title,
        "description": p.description,
        "category": p.category,
        "budget_min": None,  # 撮合平台不透露价格
        "budget_max": None,
        "deadline": p.deadline,
        "status": p.status,
        "match_count": match_count,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _match_to_dict(m: ProcurementMatch) -> dict:
    """将 ProcurementMatch 模型转为前端响应格式（匹配 ProcurementMatch 接口）"""
    return {
        "id": m.id,
        "procurement_id": m.procurement_id,
        "exhibitor_id": m.exhibitor_id,
        "exhibitor_username": None,  # will be populated by caller
        "exhibitor_company": None,   # will be populated by caller
        "message": m.message,
        "quoted_price": m.quoted_price,
        "is_accepted": m.is_accepted,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _get_match_counts(db: Session, procurement_ids: list[int]) -> dict[int, int]:
    """批量获取采购需求的匹配数量"""
    if not procurement_ids:
        return {}
    from sqlalchemy import func
    results = (
        db.query(
            ProcurementMatch.procurement_id,
            func.count(ProcurementMatch.id).label("cnt"),
        )
        .filter(ProcurementMatch.procurement_id.in_(procurement_ids))
        .group_by(ProcurementMatch.procurement_id)
        .all()
    )
    return {row.procurement_id: row.cnt for row in results}


def _paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    """构建分页响应数据"""
    return {
        "list": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }


# ============================================================
# 端点
# ============================================================

@router.get("")
def get_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """获取采购需求列表（分页 + 筛选 + 搜索）"""
    q = db.query(Procurement)

    if category:
        q = q.filter(Procurement.category == category)

    if status:
        q = q.filter(Procurement.status == status)

    if keyword:
        q = q.filter(
            or_(
                Procurement.title.ilike(f"%{keyword}%"),
                Procurement.description.ilike(f"%{keyword}%"),
            )
        )

    total = q.count()
    procurements = (
        q.order_by(Procurement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 批量获取匹配数量
    ids = [p.id for p in procurements]
    counts = _get_match_counts(db, ids)

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_procurement_to_dict(p, counts.get(p.id, 0)) for p in procurements],
            total,
            page,
            page_size,
        ),
    }


@router.get("/my")
def get_my_procurements(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的采购需求列表"""
    q = db.query(Procurement).filter(Procurement.purchaser_id == current_user.id)

    total = q.count()
    procurements = (
        q.order_by(Procurement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    ids = [p.id for p in procurements]
    counts = _get_match_counts(db, ids)

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_procurement_to_dict(p, counts.get(p.id, 0)) for p in procurements],
            total,
            page,
            page_size,
        ),
    }


@router.get("/{procurement_id}")
def get_by_id(
    procurement_id: int,
    db: Session = Depends(get_db),
):
    """获取采购需求详情"""
    p = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not p:
        raise NotFound(message="采购需求不存在")

    match_count = (
        db.query(ProcurementMatch)
        .filter(ProcurementMatch.procurement_id == procurement_id)
        .count()
    )

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _procurement_to_dict(p, match_count),
    }


@router.post("")
def create(
    data: ProcurementCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """创建采购需求（登录用户即可）"""
    p = Procurement(
        title=data.title,
        description=data.description,
        category=data.category,
        budget_min=data.budget_min,
        budget_max=data.budget_max,
        deadline=data.deadline,
        status="pending",
        purchaser_id=current_user.id,
        purchaser_name=current_user.company or current_user.nickname or current_user.username,
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    # V2.2: 发布采购赚积分
    try:
        from app.modules.identity.points import earn_points
        earn_points(current_user.id, "earn_procurement", "procurement", p.id, db)
    except: pass

    # V2.4: 通知匹配展商
    try:
        from app.models.notification import notify
        from app.models.user import User
        from app.models.category import match_category_score
        exhibitors = db.query(User).filter(User.role == "exhibitor", User.industry_domain.isnot(None)).all()
        for exh in exhibitors:
            if exh.industry_domain and p.category:
                s = match_category_score(exh.industry_domain, p.category)
                if s >= 20:
                    notify(db, exh.id, "match",
                           f"🔔 新采购需求匹配：{p.title[:30]}",
                           f"品类：{p.category}，与你的行业领域「{exh.industry_domain}」匹配",
                           f"/procurements/{p.id}")
    except: pass

    return {
        "success": True,
        "code": "OK",
        "message": "采购需求创建成功",
        "data": _procurement_to_dict(p, 0),
    }


@router.put("/{procurement_id}")
def update(
    procurement_id: int,
    data: ProcurementUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """更新采购需求（仅创建者或管理员）"""
    p = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not p:
        raise NotFound(message="采购需求不存在")

    # 权限检查：仅创建者或管理员可编辑
    if p.purchaser_id != current_user.id and current_user.role != "admin":
        raise Forbidden(message="无权编辑此采购需求")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if hasattr(p, field):
            setattr(p, field, value)

    db.commit()
    db.refresh(p)

    match_count = (
        db.query(ProcurementMatch)
        .filter(ProcurementMatch.procurement_id == procurement_id)
        .count()
    )

    return {
        "success": True,
        "code": "OK",
        "message": "采购需求更新成功",
        "data": _procurement_to_dict(p, match_count),
    }


@router.delete("/{procurement_id}")
def delete(
    procurement_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """删除采购需求（仅创建者或管理员）"""
    p = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not p:
        raise NotFound(message="采购需求不存在")

    if p.purchaser_id != current_user.id and current_user.role not in ("admin",):
        raise Forbidden(message="无权删除此采购需求")

    db.delete(p)
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "采购需求已删除",
        "data": None,
    }


@router.post("/{procurement_id}/cancel")
def cancel(
    procurement_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """取消采购需求（仅创建者或管理员）"""
    p = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not p:
        raise NotFound(message="采购需求不存在")

    if p.purchaser_id != current_user.id and current_user.role not in ("admin",):
        raise Forbidden(message="无权取消此采购需求")

    if p.status == "cancelled":
        raise BadRequest(message="该采购需求已被取消")

    p.status = "cancelled"
    db.commit()
    db.refresh(p)

    match_count = (
        db.query(ProcurementMatch)
        .filter(ProcurementMatch.procurement_id == procurement_id)
        .count()
    )

    return {
        "success": True,
        "code": "OK",
        "message": "采购需求已取消",
        "data": _procurement_to_dict(p, match_count),
    }


# ============================================================
# 匹配相关端点
# ============================================================

@router.get("/{procurement_id}/matches")
def get_matches(
    procurement_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取采购需求的所有匹配记录（仅需求创建者或管理员）"""
    p = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not p:
        raise NotFound(message="采购需求不存在")

    # 归属校验：仅需求创建者或管理员可查看匹配与报价
    if p.purchaser_id != current_user.id and current_user.role != "admin":
        raise Forbidden(message="无权查看此采购需求的匹配")

    matches = (
        db.query(ProcurementMatch)
        .filter(ProcurementMatch.procurement_id == procurement_id)
        .order_by(ProcurementMatch.created_at.desc())
        .all()
    )

    # 批量获取展商用户信息
    exhibitor_ids = [m.exhibitor_id for m in matches]
    exhibitor_map = {}
    if exhibitor_ids:
        users = db.query(User).filter(User.id.in_(exhibitor_ids)).all()
        exhibitor_map = {u.id: u for u in users}

    match_list = []
    for m in matches:
        d = _match_to_dict(m)
        user = exhibitor_map.get(m.exhibitor_id)
        if user:
            d["exhibitor_username"] = user.username
            d["exhibitor_company"] = user.company
        match_list.append(d)

    match_count = len(match_list)

    return {
        "success": True,
        "code": "OK",
        "message": "获取匹配列表成功",
        "data": {
            "procurement": _procurement_to_dict(p, match_count),
            "matches": match_list,
        },
    }


@router.post("/{procurement_id}/matches")
def create_match(
    procurement_id: int,
    data: MatchCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """创建匹配（展商对采购需求投标）

    仅展商角色可提交匹配。
    """
    if current_user.role != "exhibitor":
        raise Forbidden(message="仅展商可提交匹配")

    p = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not p:
        raise NotFound(message="采购需求不存在")

    if p.status not in ("pending",):
        raise BadRequest(message="该采购需求当前状态不可匹配")

    # 检查是否已经提交过匹配
    existing = (
        db.query(ProcurementMatch)
        .filter(
            ProcurementMatch.procurement_id == procurement_id,
            ProcurementMatch.exhibitor_id == current_user.id,
        )
        .first()
    )
    if existing:
        raise BadRequest(message="您已对该采购需求提交过匹配")

    # 如果指定了 product_id，验证展品存在且属于当前展商
    if data.product_id is not None:
        product = db.query(Product).filter(Product.id == data.product_id).first()
        if not product:
            raise NotFound(message="展品不存在")
        if product.exhibitor_id != current_user.id:
            raise Forbidden(message="该展品不属于您")

    match = ProcurementMatch(
        procurement_id=procurement_id,
        exhibitor_id=current_user.id,
        product_id=data.product_id,
        message=data.message,
        quoted_price=data.quoted_price,
        is_accepted=False,
    )
    db.add(match)

    # 更新采购需求状态为 matched（如果有匹配）
    if p.status == "pending":
        p.status = "matched"

    db.commit()
    db.refresh(match)

    # V2.9: 通知采购方有展商应标
    try:
        from app.models.notification import notify
        notify(db, p.purchaser_id, "bid",
               f"📩 {current_user.company or current_user.username} 响应了你的采购「{p.title[:20]}」",
               f"报价：¥{data.quoted_price or '面议'}", f"/procurements/{procurement_id}")
    except: pass

    # 构建响应（含展商信息）
    result = _match_to_dict(match)
    result["exhibitor_username"] = current_user.username
    result["exhibitor_company"] = current_user.company

    match_count = (
        db.query(ProcurementMatch)
        .filter(ProcurementMatch.procurement_id == procurement_id)
        .count()
    )

    return {
        "success": True,
        "code": "OK",
        "message": "匹配提交成功",
        "data": {
            "match": result,
            "procurement": _procurement_to_dict(p, match_count),
        },
    }


@router.post("/{procurement_id}/matches/{match_id}/accept")
def accept_match(
    procurement_id: int,
    match_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """接受匹配（采购方接受展商的投标）

    仅采购需求的发布者可以接受匹配。
    """
    p = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not p:
        raise NotFound(message="采购需求不存在")

    if p.purchaser_id != current_user.id:
        raise Forbidden(message="仅采购需求发布者可接受匹配")

    if p.status == "cancelled":
        raise BadRequest(message="该采购需求已取消")

    match = (
        db.query(ProcurementMatch)
        .filter(
            ProcurementMatch.id == match_id,
            ProcurementMatch.procurement_id == procurement_id,
        )
        .first()
    )
    if not match:
        raise NotFound(message="匹配记录不存在")

    if match.is_accepted:
        raise BadRequest(message="该匹配已被接受")

    # 接受此匹配
    match.is_accepted = True

    # 拒绝同一采购需求的其他匹配
    db.query(ProcurementMatch).filter(
        ProcurementMatch.procurement_id == procurement_id,
        ProcurementMatch.id != match_id,
    ).update({"is_accepted": False})

    # 更新采购需求状态为 completed
    p.status = "completed"

    db.commit()
    db.refresh(match)

    # 通知中标展商（撮合成功消息；notify 自提交，失败不影响主流程）
    try:
        from app.models.notification import notify
        notify(db, match.exhibitor_id, "match",
               f"恭喜！您的应标已被买家接受：{p.title}",
               f"买家已接受您的投标" + (f"（报价 {match.quoted_price} 元）" if match.quoted_price else "") + "，采购需求已完结，请尽快与买家对接。",
               "/exhibitor/procurement-matches")
    except Exception:
        pass

    # 构建响应（含展商信息）
    result = _match_to_dict(match)
    exhibitor = db.query(User).filter(User.id == match.exhibitor_id).first()
    if exhibitor:
        result["exhibitor_username"] = exhibitor.username
        result["exhibitor_company"] = exhibitor.company

    match_count = (
        db.query(ProcurementMatch)
        .filter(ProcurementMatch.procurement_id == procurement_id)
        .count()
    )

    return {
        "success": True,
        "code": "OK",
        "message": "已接受匹配",
        "data": {
            "match": result,
            "procurement": _procurement_to_dict(p, match_count),
        },
    }


# ============================================================
# 推荐匹配端点
# ============================================================

def _product_to_dict(p) -> dict:
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "category": p.category, "price": p.price, "unit": p.unit,
        "status": p.status, "exhibitor_id": p.exhibitor_id,
        "exhibitor_name": p.exhibitor_name, "images": p.images,
        "booth_id": p.booth_id, "exhibition_id": p.exhibition_id,
        "specs": p.specs, "created_at": p.created_at.isoformat() if p.created_at else None,
    }

@router.get("/{procurement_id}/recommendations")
def get_recommendations(
    procurement_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from app.models.category import match_category_score
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise NotFound(message="采购需求不存在")

    # 归属校验：仅需求创建者或管理员可查看推荐
    if proc.purchaser_id != current_user.id and current_user.role != "admin":
        raise Forbidden(message="无权查看此采购需求的推荐")

    products = db.query(Product).filter(Product.status == "published").order_by(Product.created_at.desc()).limit(500).all()
    bmin = proc.budget_min
    bmax = proc.budget_max
    result = []

    for p in products:
        score = 0
        reasons = []
        cat_score = match_category_score(p.category or '', proc.category or '')
        if cat_score >= 50: score += 50; reasons.append('品类精确匹配')
        elif cat_score >= 30: score += 30; reasons.append('同行业大类')
        elif cat_score >= 10: score += 10; reasons.append('品类相关')

        if proc.exhibition_id and p.exhibition_id == proc.exhibition_id:
            score += 15; reasons.append('同展会')

        if p.price and bmin and bmax and bmin <= p.price <= bmax:
            score += 10; reasons.append('预算匹配')

        score += 5
        if score > 5:
            d = _product_to_dict(p)
            d["match_score"] = score
            d["match_reasons"] = reasons
            result.append(d)

    if not result:
        products2 = db.query(Product).filter(Product.status == "published").order_by(Product.created_at.desc()).limit(limit).all()
        for p in products2:
            d = _product_to_dict(p)
            d["match_score"] = 1
            d["match_reasons"] = ["推荐展品"]
            result.append(d)
    else:
        result.sort(key=lambda x: x["match_score"], reverse=True)
        result = result[:limit]

    return {"success": True, "code": "OK", "message": "获取成功", "data": result}



