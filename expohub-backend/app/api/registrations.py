"""
展会报名路由（Registrations）

前端 registration.ts 期望的端点：
- POST   /registrations              报名参加展会
- GET    /registrations/my           我的报名列表
- DELETE /registrations/{exhibition_id}  取消报名
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.user import User
from app.models.exhibition import Exhibition
from app.models.registration import Registration
from app.api.deps import get_current_active_user
from app.core.exceptions import NotFound, BadRequest, Conflict

router = APIRouter(prefix="/registrations", tags=["展会报名"])


# ============================================================
# Pydantic Schemas
# ============================================================

class RegisterRequest(BaseModel):
    """报名请求"""
    exhibition_id: int
    is_favorite: bool = False
    is_registered: bool = True


# ============================================================
# 辅助函数
# ============================================================

def _registration_to_dict(reg: Registration, exhibition: Optional[Exhibition] = None) -> dict:
    """将 Registration 模型转为前端响应格式"""
    result = {
        "id": reg.id,
        "visitor_id": reg.visitor_id,
        "exhibition_id": reg.exhibition_id,
        "is_favorite": reg.is_favorite,
        "is_registered": reg.is_registered,
        "ticket_code": reg.ticket_code,
        "check_in_at": reg.check_in_at,
        "created_at": reg.created_at.isoformat() if reg.created_at else None,
    }

    if exhibition:
        result["exhibition"] = {
            "id": exhibition.id,
            "title": exhibition.title,
            "description": exhibition.description,
            "cover_image": exhibition.cover_image,
            "start_date": exhibition.start_date,
            "end_date": exhibition.end_date,
            "location": exhibition.location,
            "status": exhibition.status,
            "organizer_name": exhibition.organizer_name,
            "created_at": exhibition.created_at.isoformat() if exhibition.created_at else None,
        }

    return result


# ============================================================
# 端点
# ============================================================

@router.post("")
def register(
    data: RegisterRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """报名参加展会

    前端调用：POST /registrations
    请求体：{ exhibition_id, is_favorite?, is_registered? }

    如果已报名则返回冲突。
    """
    # 验证展会存在
    exhibition = db.query(Exhibition).filter(Exhibition.id == data.exhibition_id).first()
    if not exhibition:
        raise NotFound(message="展会不存在")

    # 检查是否已报名
    existing = (
        db.query(Registration)
        .filter(
            Registration.visitor_id == current_user.id,
            Registration.exhibition_id == data.exhibition_id,
        )
        .first()
    )
    if existing:
        raise Conflict(message="您已报名该展会")

    # 生成电子票码
    import uuid
    ticket_code = f"TKT-{uuid.uuid4().hex[:8].upper()}"

    now = datetime.now(timezone.utc)

    registration = Registration(
        visitor_id=current_user.id,
        exhibition_id=data.exhibition_id,
        is_favorite=data.is_favorite,
        is_registered=data.is_registered,
        ticket_code=ticket_code,
        created_at=now,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)

    # V2.2: 报名赚积分
    try:
        from app.api.points import earn_points
        earn_points(current_user.id, "earn_registration", "registration", registration.id, db)
    except: pass

    # V2.4: 通知展会主办方
    try:
        from app.models.notification import notify
        if exhibition.organizer_id:
            notify(db, exhibition.organizer_id, "system",
                   f"📋 {current_user.nickname or current_user.username} 报名了「{exhibition.title[:20]}」",
                   link=f"/organizer/exhibitions/{exhibition.id}/registrations")
    except: pass

    return {
        "success": True,
        "code": "OK",
        "message": "报名成功",
        "data": _registration_to_dict(registration, exhibition),
    }


@router.get("/my")
def get_my_registrations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的报名列表（分页）

    前端调用：GET /registrations/my?page=1&page_size=9
    返回报名记录，附带展会信息。
    """
    q = db.query(Registration).filter(Registration.visitor_id == current_user.id)
    total = q.count()

    registrations = (
        q.order_by(Registration.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 批量查询关联展会
    exhibition_ids = [r.exhibition_id for r in registrations]
    exhibitions_map = {}
    if exhibition_ids:
        exhibitions = (
            db.query(Exhibition)
            .filter(Exhibition.id.in_(exhibition_ids))
            .all()
        )
        exhibitions_map = {e.id: e for e in exhibitions}

    items = [
        _registration_to_dict(r, exhibitions_map.get(r.exhibition_id))
        for r in registrations
    ]

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": {
            "list": items,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": (total + page_size - 1) // page_size if page_size > 0 else 0,
        },
    }



@router.get("")
def get_registrations(
    exhibition_id: int = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # Only organizer of this exhibition or admin can view registrations
    exhibition = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exhibition:
        raise NotFound(message="展会不存在")
    if exhibition.organizer_id != current_user.id and current_user.role not in ("admin",):
        raise Forbidden(message="无权查看该展会的报名")

    q = db.query(Registration).filter(Registration.exhibition_id == exhibition_id)
    total = q.count()
    registrations = q.order_by(Registration.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()

    items = []
    for reg in registrations:
        d = _registration_to_dict(reg)
        user = db.query(User).filter(User.id == reg.visitor_id).first()
        d["username"] = user.username if user else "unknown"
        d["email"] = user.email if user else ""
        items.append(d)

    return {"success": True, "code": "OK", "message": "获取成功",
            "data": {"list": items, "total": total, "page": page, "pageSize": page_size, "totalPages": (total+page_size-1)//page_size}}


@router.get("/favorites")
def get_favorites(current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    regs = db.query(Registration).filter(Registration.visitor_id == current_user.id, Registration.is_favorite == True).all()
    items = [_registration_to_dict(r) for r in regs]
    return {"success": True, "data": {"list": items, "total": len(items)}}

@router.post("/favorites/{exhibition_id}")
def toggle_favorite(exhibition_id: int, current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    reg = db.query(Registration).filter(Registration.visitor_id == current_user.id, Registration.exhibition_id == exhibition_id).first()
    if reg:
        reg.is_favorite = not reg.is_favorite
        db.commit()
        return {"success": True, "data": {"is_favorite": reg.is_favorite}}
    reg = Registration(visitor_id=current_user.id, exhibition_id=exhibition_id, is_favorite=True, is_registered=False)
    db.add(reg); db.commit()
    return {"success": True, "data": {"is_favorite": True}}

@router.delete("/{exhibition_id}")
def cancel_registration(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """取消报名

    前端调用：DELETE /registrations/{exhibitionId}
    """
    registration = (
        db.query(Registration)
        .filter(
            Registration.visitor_id == current_user.id,
            Registration.exhibition_id == exhibition_id,
        )
        .first()
    )
    if not registration:
        raise NotFound(message="未找到报名记录")

    db.delete(registration)
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "已取消报名",
        "data": None,
    }
