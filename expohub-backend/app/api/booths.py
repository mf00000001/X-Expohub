"""
展位路由（Booths）

端点：
- GET    /booths       展位列表
- GET    /booths/my    我的展位（必须在 :id 之前）
- GET    /booths/:id   展位详情
- POST   /booths       创建展位
- PUT    /booths/:id   更新展位
- DELETE /booths/:id   删除展位
- POST   /booths/:id/apply  申请展位
- POST   /booths/book       预订展位（from frontend）
- POST   /booths/:id/assign 分配展位给展商（from frontend）
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.exceptions import NotFound, Forbidden, BadRequest, Conflict
from app.models.base import get_db
from app.models.user import User
from app.models.booth import Booth
from app.models.exhibition import Exhibition
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/booths", tags=["展位"])


# ============================================================
# Pydantic Schemas
# ============================================================

class BoothCreate(BaseModel):
    """创建展位请求"""
    exhibition_id: int
    booth_number: str
    size: Optional[str] = None
    location_area: Optional[str] = None
    price: Optional[float] = None
    status: Optional[str] = "available"
    description: Optional[str] = None
    # Frontend-expected extra fields (accepted but may map to model columns)
    name: Optional[str] = None
    area: Optional[float] = None
    floor: Optional[int] = None
    zone: Optional[str] = None


class BoothUpdate(BaseModel):
    """更新展位请求（所有字段可选）"""
    booth_number: Optional[str] = None
    size: Optional[str] = None
    location_area: Optional[str] = None
    price: Optional[float] = None
    status: Optional[str] = None
    description: Optional[str] = None
    exhibitor_name: Optional[str] = None
    company_name: Optional[str] = None
    # Frontend-expected extra fields
    name: Optional[str] = None
    area: Optional[float] = None
    floor: Optional[int] = None
    zone: Optional[str] = None


class BoothBook(BaseModel):
    """预订展位请求（from frontend）"""
    booth_id: int


class BoothAssign(BaseModel):
    """分配展位请求（from frontend）"""
    exhibitor_id: int


def _booth_to_dict(booth: Booth) -> dict:
    """将 Booth 模型转为前端响应格式

    前端 BoothItem 期望字段：
      id, exhibition_id, exhibitor_id, booth_number, name, description,
      area, price, floor, zone, status, created_at, updated_at
    """
    return {
        "id": booth.id,
        "exhibition_id": booth.exhibition_id,
        "booth_number": booth.booth_number,
        "exhibitor_id": booth.exhibitor_id,
        "exhibitor_name": booth.exhibitor_name,
        "company_name": booth.company_name,
        "size": booth.size,
        "location_area": booth.location_area,
        "price": None,  # 公开API不透露价格
        "status": booth.status,
        "description": booth.description,
        # Frontend-expected fields (model doesn't have these columns; provide defaults)
        "name": getattr(booth, 'name', None) or booth.booth_number or "",
        "area": getattr(booth, 'area', None) or 0,
        "floor": getattr(booth, 'floor', None) or 0,
        "zone": getattr(booth, 'zone', None) or booth.location_area or "",
        "created_at": booth.created_at.isoformat() if booth.created_at else None,
        "updated_at": booth.updated_at.isoformat() if booth.updated_at else None,
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
    exhibition_id: Optional[int] = Query(default=None),
    zone: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """获取展位列表（分页 + 按展会/zone/状态筛选）"""
    q = db.query(Booth)

    if exhibition_id:
        q = q.filter(Booth.exhibition_id == exhibition_id)

    if status:
        q = q.filter(Booth.status == status)

    if zone:
        # Model has no zone column; filter on location_area as closest proxy
        q = q.filter(Booth.location_area == zone)

    # Filter: only show booths from approved exhibitors in public listing
    q = q.outerjoin(User, Booth.exhibitor_id == User.id).filter(
        (User.id == None) | (User.role != "exhibitor") | (User.organizer_status == None) | (User.organizer_status == "approved")
    )

    total = q.count()
    booths = q.order_by(Booth.booth_number).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_booth_to_dict(b) for b in booths], total, page, page_size
        ),
    }


@router.get("/my")
def get_my_booths(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的展位列表"""
    q = db.query(Booth).filter(Booth.exhibitor_id == current_user.id)
    total = q.count()
    booths = q.order_by(Booth.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_booth_to_dict(b) for b in booths], total, page, page_size
        ),
    }


@router.get("/{booth_id}")
def get_by_id(
    booth_id: int,
    db: Session = Depends(get_db),
):
    """获取展位详情"""
    booth = db.query(Booth).filter(Booth.id == booth_id).first()
    if not booth:
        raise NotFound(message="展位不存在")

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _booth_to_dict(booth),
    }


@router.post("")
def create(
    data: BoothCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """创建展位（主办方/管理员）"""
    if current_user.role not in ("organizer", "admin"):
        raise Forbidden(message="仅主办方可创建展位")

    # 检查展会是否存在
    exh = db.query(Exhibition).filter(Exhibition.id == data.exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    # 检查展位编号唯一性
    existing = db.query(Booth).filter(
        Booth.exhibition_id == data.exhibition_id,
        Booth.booth_number == data.booth_number,
    ).first()
    if existing:
        raise Conflict(message=f"展位编号 {data.booth_number} 已存在")

    booth = Booth(
        exhibition_id=data.exhibition_id,
        booth_number=data.booth_number,
        size=data.size,
        location_area=data.location_area or data.zone,
        price=data.price,
        status=data.status or "available",
        description=data.description or data.name,
    )
    db.add(booth)
    db.commit()
    db.refresh(booth)

    return {
        "success": True,
        "code": "OK",
        "message": "展位创建成功",
        "data": _booth_to_dict(booth),
    }


@router.put("/{booth_id}")
def update(
    booth_id: int,
    data: BoothUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """更新展位信息"""
    booth = db.query(Booth).filter(Booth.id == booth_id).first()
    if not booth:
        raise NotFound(message="展位不存在")

    # 权限：主办方/管理员 或 展位拥有者
    is_owner = booth.exhibitor_id == current_user.id
    is_admin = current_user.role in ("organizer", "admin")
    if not is_owner and not is_admin:
        raise Forbidden(message="无权编辑此展位")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        # Map frontend fields to model columns
        if field == "zone" and hasattr(booth, "location_area"):
            setattr(booth, "location_area", value)
        elif field == "name" and hasattr(booth, "description"):
            # Only map name→description if description not in updates
            if "description" not in updates:
                setattr(booth, "description", value)
        elif hasattr(booth, field):
            setattr(booth, field, value)

    db.commit()
    db.refresh(booth)

    return {
        "success": True,
        "code": "OK",
        "message": "展位更新成功",
        "data": _booth_to_dict(booth),
    }


@router.delete("/{booth_id}")
def delete(
    booth_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """删除展位"""
    booth = db.query(Booth).filter(Booth.id == booth_id).first()
    if not booth:
        raise NotFound(message="展位不存在")

    if current_user.role not in ("organizer", "admin"):
        raise Forbidden(message="无权删除展位")

    db.delete(booth)
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "展位已删除",
        "data": None,
    }


@router.post("/{booth_id}/apply")
def apply(
    booth_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """申请展位（展商申请入驻）"""
    if current_user.role not in ("exhibitor",):
        raise Forbidden(message="仅展商可申请展位")

    booth = db.query(Booth).filter(Booth.id == booth_id).first()
    if not booth:
        raise NotFound(message="展位不存在")

    if booth.status != "available":
        raise BadRequest(message="该展位不可申请")

    if booth.exhibitor_id is not None:
        raise Conflict(message="该展位已被占用")

    booth.exhibitor_id = current_user.id
    booth.exhibitor_name = current_user.nickname or current_user.username
    booth.company_name = current_user.company
    booth.status = "reserved"

    db.commit()
    db.refresh(booth)

    return {
        "success": True,
        "code": "OK",
        "message": "展位申请成功",
        "data": _booth_to_dict(booth),
    }


# ============================================================
# 新增端点：/book 和 /assign（前端直接调用）
# ============================================================

@router.post("/book")
def book(
    data: BoothBook,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """预订展位（前端 /booths/book 路由）

    请求体: { booth_id: number }
    任何已登录用户均可预订可用展位。
    """
    booth = db.query(Booth).filter(Booth.id == data.booth_id).first()
    if not booth:
        raise NotFound(message="展位不存在")

    if booth.status != "available":
        raise BadRequest(message="该展位不可预订")

    if booth.exhibitor_id is not None:
        raise Conflict(message="该展位已被占用")

    booth.exhibitor_id = current_user.id
    booth.exhibitor_name = current_user.nickname or current_user.username
    booth.company_name = current_user.company
    booth.status = "reserved"

    db.commit()
    db.refresh(booth)

    return {
        "success": True,
        "code": "OK",
        "message": "展位预订成功",
        "data": _booth_to_dict(booth),
    }


@router.post("/{booth_id}/assign")
def assign(
    booth_id: int,
    data: BoothAssign,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """分配展位给指定展商（主办方/管理员专用）

    URL:   POST /booths/{booth_id}/assign
    请求体: { exhibitor_id: number }
    """
    if current_user.role not in ("organizer", "admin"):
        raise Forbidden(message="仅主办方可分配展位")

    booth = db.query(Booth).filter(Booth.id == booth_id).first()
    if not booth:
        raise NotFound(message="展位不存在")

    exhibitor = db.query(User).filter(User.id == data.exhibitor_id).first()
    if not exhibitor:
        raise NotFound(message="展商用户不存在")

    if exhibitor.role not in ("exhibitor", "admin", "organizer"):
        raise BadRequest(message="目标用户不是展商")

    booth.exhibitor_id = exhibitor.id
    booth.exhibitor_name = exhibitor.nickname or exhibitor.username
    booth.company_name = exhibitor.company
    if booth.status == "available":
        booth.status = "reserved"

    db.commit()
    db.refresh(booth)

    return {
        "success": True,
        "code": "OK",
        "message": "展位分配成功",
        "data": _booth_to_dict(booth),
    }
