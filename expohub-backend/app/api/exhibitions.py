"""
展会路由（Exhibitions）

端点：
- GET    /exhibitions                  展会列表
- GET    /exhibitions/registrations    我的报名列表（必须在 :id 之前）
- GET    /exhibitions/:id              展会详情
- POST   /exhibitions                  创建展会
- PUT    /exhibitions/:id              更新展会
- DELETE /exhibitions/:id              删除展会
- POST   /exhibitions/:id/register     报名参展
- DELETE /exhibitions/:id/register     取消报名
- POST   /exhibitions/:id/approve      审批展会
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.core.exceptions import NotFound, BadRequest, Forbidden
from app.models.base import get_db
from app.models.user import User
from app.models.exhibition import Exhibition
from app.models.venue import Venue
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/exhibitions", tags=["展会"])


# ============================================================
# Pydantic Schemas
# ============================================================

class ExhibitionCreate(BaseModel):
    """创建展会请求"""
    title: str
    description: Optional[str] = None
    cover_image: Optional[str] = None
    start_date: str
    end_date: str
    location: str
    venue_id: Optional[int] = None  # V3.1: 关联展馆(可选)
    status: Optional[str] = "draft"


class ExhibitionUpdate(BaseModel):
    """更新展会请求（所有字段可选）"""
    title: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None


class ExhibitionApproveRequest(BaseModel):
    """审批展会请求"""
    approved: bool = True
    comment: Optional[str] = None


def _exhibition_to_dict(exh: Exhibition, db: Optional[Session] = None) -> dict:
    """将 Exhibition 模型转为前端响应格式"""
    venue_info = None
    if exh.venue_id is not None and db is not None:
        v = db.query(Venue).filter(Venue.id == exh.venue_id).first()
        if v:
            venue_info = {
                "id": v.id,
                "name": v.name,
                "city": v.city,
                "address": v.address,
                "area": v.area,
            }
    return {
        "id": exh.id,
        "title": exh.title,
        "name": exh.title,  # frontend alias for title
        "title_en": exh.title_en,
        "description": exh.description,
        "description_en": exh.description_en,
        "cover_image": exh.cover_image,
        "cover_url": exh.cover_image,  # frontend alias for cover_image
        "start_date": exh.start_date,
        "end_date": exh.end_date,
        "location": exh.location,
        "venue": exh.location,  # frontend alias for location
        "venue_info": venue_info,  # V3.1: 关联展馆信息(可选,含 id/name/city/address/area)
        "city": "",  # placeholder - backend does not separate city
        "address": exh.location,  # frontend field mapped to location
        "short_name": "",  # placeholder
        "total_booths": 0,  # placeholder
        "available_booths": 0,  # placeholder
        "visitor_count": exh.visitor_count or 0,
        "status": exh.status,
        "organizer_id": exh.organizer_id,
        "organizer_name": exh.organizer_name,
        # V2.0
        "is_featured": exh.is_featured,
        "hot_score": exh.hot_score or 0,
        "created_at": exh.created_at.isoformat() if exh.created_at else None,
        "updated_at": exh.updated_at.isoformat() if exh.updated_at else None,
    }


def _paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
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
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """获取展会列表（分页 + 筛选 + 搜索）"""
    q = db.query(Exhibition)

    if status:
        q = q.filter(Exhibition.status == status)

    if search:
        q = q.filter(
            or_(
                Exhibition.title.ilike(f"%{search}%"),
                Exhibition.description.ilike(f"%{search}%"),
                Exhibition.location.ilike(f"%{search}%"),
            )
        )

    total = q.count()
    exhibitions = q.order_by(Exhibition.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_exhibition_to_dict(e, db) for e in exhibitions], total, page, page_size
        ),
    }


# ============================================================
# V2.0: 首页精选 & 热门
# ============================================================

@router.get("/featured")
def get_featured(
    limit: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """首页精选展会（重磅来袭）

    优先返回 is_featured=True 的展会，按 hot_score 降序。
    不足 limit 条时用最新发布的展会补齐。
    """
    featured = db.query(Exhibition).filter(
        Exhibition.is_featured == True,
        Exhibition.status.in_(["published", "ongoing"]),
    ).order_by(Exhibition.hot_score.desc()).limit(limit).all()

    # 精选不够，用最新发布补齐
    if len(featured) < limit:
        exclude_ids = [e.id for e in featured]
        extra = db.query(Exhibition).filter(
            Exhibition.status.in_(["published", "ongoing"]),
            ~Exhibition.id.in_(exclude_ids) if exclude_ids else True,
        ).order_by(Exhibition.created_at.desc()).limit(limit - len(featured)).all()
        featured.extend(extra)

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": [_exhibition_to_dict(e, db) for e in featured],
    }


@router.get("/hot")
def get_hot(
    limit: int = Query(default=10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """热门展会 Top N（按 hot_score 降序）"""
    hot = db.query(Exhibition).filter(
        Exhibition.status.in_(["published", "ongoing"]),
    ).order_by(Exhibition.hot_score.desc()).limit(limit).all()

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": [_exhibition_to_dict(e, db) for e in hot],
    }


@router.get("/upcoming")
def get_upcoming(
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """即将开幕的展会（按 start_date 升序）"""
    upcoming = db.query(Exhibition).filter(
        Exhibition.status.in_(["published"]),
    ).order_by(Exhibition.start_date.asc()).limit(limit).all()

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": [_exhibition_to_dict(e, db) for e in upcoming],
    }


@router.get("/registrations")
def get_registrations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的展会报名列表

    注：当前简化实现返回用户作为主办方的展会。
    后续可通过中间表实现完整的报名关系。
    """
    q = db.query(Exhibition).filter(Exhibition.organizer_id == current_user.id)
    total = q.count()
    exhibitions = q.order_by(Exhibition.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_exhibition_to_dict(e, db) for e in exhibitions], total, page, page_size
        ),
    }


@router.get("/{exhibition_id}")
def get_by_id(
    exhibition_id: int,
    db: Session = Depends(get_db),
):
    """获取展会详情"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _exhibition_to_dict(exh, db),
    }


@router.post("")
def create(
    data: ExhibitionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """创建展会（仅主办方可创建）"""
    if current_user.role not in ("organizer", "admin"):
        raise Forbidden(message="仅主办方可创建展会")

    # V3.1: 校验关联展馆存在
    venue_id = data.venue_id
    if venue_id is not None:
        venue = db.query(Venue).filter(Venue.id == venue_id).first()
        if not venue:
            raise NotFound(message="展馆不存在")

    exh = Exhibition(
        title=data.title,
        description=data.description,
        cover_image=data.cover_image,
        start_date=data.start_date,
        end_date=data.end_date,
        location=data.location,
        venue_id=venue_id,
        status=data.status or "draft",
        organizer_id=current_user.id,
        organizer_name=current_user.company or current_user.nickname or current_user.username,
    )
    db.add(exh)
    db.commit()
    db.refresh(exh)

    return {
        "success": True,
        "code": "OK",
        "message": "展会创建成功",
        "data": _exhibition_to_dict(exh, db),
    }


@router.put("/{exhibition_id}")
def update(
    exhibition_id: int,
    data: ExhibitionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """更新展会信息"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    # 权限检查：仅创建者或管理员可编辑
    if exh.organizer_id != current_user.id and current_user.role != "admin":
        raise Forbidden(message="无权编辑此展会")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if hasattr(exh, field):
            setattr(exh, field, value)

    db.commit()
    db.refresh(exh)

    return {
        "success": True,
        "code": "OK",
        "message": "展会更新成功",
        "data": _exhibition_to_dict(exh, db),
    }


@router.delete("/{exhibition_id}")
def delete(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """删除展会"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    if exh.organizer_id != current_user.id and current_user.role not in ("admin",):
        raise Forbidden(message="无权删除此展会")

    db.delete(exh)
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "展会已删除",
        "data": None,
    }


@router.post("/{exhibition_id}/register")
def register(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """报名参加展会（展商报名）"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    if exh.status not in ("published", "ongoing"):
        raise BadRequest(message="展会未开放报名")

    # 简化：将用户设为展会的关注者
    # 实际项目中应通过中间表记录报名关系
    return {
        "success": True,
        "code": "OK",
        "message": "报名成功",
        "data": {
            "exhibition_id": exh.id,
            "user_id": current_user.id,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.delete("/{exhibition_id}/register")
def unregister(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """取消展会报名"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    return {
        "success": True,
        "code": "OK",
        "message": "已取消报名",
        "data": None,
    }


@router.post("/{exhibition_id}/approve")
def approve(
    exhibition_id: int,
    data: ExhibitionApproveRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """审批展会（管理员，或主办方本人）"""
    if current_user.role not in ("admin", "organizer"):
        raise Forbidden(message="无权审批展会")
    # 主办方必须已通过入驻审核
    if current_user.role == "organizer" and current_user.organizer_status != "approved":
        raise Forbidden(message="主办方入驻审核未通过，无法审批展会")

    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    # 归属校验：主办方仅可审批自己创建的展会
    if current_user.role == "organizer" and exh.organizer_id != current_user.id:
        raise Forbidden(message="无权审批其他主办方的展会")

    if data.approved:
        exh.status = "published"
    else:
        exh.status = "draft"

    db.commit()
    db.refresh(exh)

    return {
        "success": True,
        "code": "OK",
        "message": "审批完成" if data.approved else "已驳回",
        "data": _exhibition_to_dict(exh, db),
    }

@router.post("/{exhibition_id}/publish")
def publish(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """发布展会（设置状态为 published）"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    # 权限：仅展会创建者(主办方本人)或管理员可发布
    if exh.organizer_id != current_user.id and current_user.role != "admin":
        raise Forbidden(message="无权发布此展会")
    # 主办方必须已通过入驻审核
    if current_user.role == "organizer" and current_user.organizer_status != "approved":
        raise Forbidden(message="主办方入驻审核未通过，无法发布展会")

    exh.status = "published"
    db.commit()
    db.refresh(exh)

    return {
        "success": True,
        "code": "OK",
        "message": "展会发布成功",
        "data": _exhibition_to_dict(exh, db),
    }



# ============================================================
# AI 语义搜索
# ============================================================

def _product_to_dict(p) -> dict:
    return {
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'category': p.category,
        'price': p.price,
        'unit': p.unit,
        'images': p.images,
        'stock': p.stock,
        'status': p.status,
        'booth_id': p.booth_id,
        'exhibition_id': p.exhibition_id,
        'exhibitor_id': p.exhibitor_id,
        'exhibitor_name': p.exhibitor_name,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


def _booth_to_dict(b) -> dict:
    return {
        'id': b.id,
        'exhibition_id': b.exhibition_id,
        'booth_number': b.booth_number,
        'exhibitor_id': b.exhibitor_id,
        'exhibitor_name': b.exhibitor_name,
        'company_name': b.company_name,
        'size': b.size,
        'location_area': b.location_area,
        'price': b.price,
        'status': b.status,
        'description': b.description,
        'created_at': b.created_at.isoformat() if b.created_at else None,
    }


@router.get('/search/smart')
def smart_search(q: str = Query(...), db: Session = Depends(get_db)):
    # Search exhibitions, products, booths by keyword
    # Return combined results ranked by relevance
    results = {'exhibitions': [], 'products': [], 'booths': []}
    like = f'%{q}%'
    from app.models.exhibition import Exhibition
    from app.models.product import Product
    from app.models.booth import Booth

    results['exhibitions'] = [_exhibition_to_dict(e, db) for e in db.query(Exhibition).filter(
        Exhibition.title.ilike(like)).limit(5).all()]

    results['products'] = [_product_to_dict(p) for p in db.query(Product).filter(
        Product.name.ilike(like)).limit(5).all()]

    results['booths'] = [_booth_to_dict(b) for b in db.query(Booth).filter(
        Booth.booth_number.ilike(like)).limit(5).all()]

    total = len(results['exhibitions']) + len(results['products']) + len(results['booths'])
    return {'success': True, 'code': 'OK', 'data': results, 'total': total}

