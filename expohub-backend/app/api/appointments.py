"""V2.9: 展会预约 — 买家约展商线下见面（V3.0 落库版）

原实现为内存存储（appointments_db 列表），现已落库（appointments 表），
支持持久化、事务；后续配对码核销状态机在此基础上扩展。
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.user import User
from app.models.exhibition import Exhibition
from app.models.appointment import Appointment
from app.models.notification import notify
from app.api.deps import get_current_active_user
from app.core.exceptions import NotFound

router = APIRouter(prefix="/appointments", tags=["预约"])


class ApptRequest(BaseModel):
    exhibitor_id: int
    exhibition_id: int
    time_slot: Optional[str] = None  # "上午/下午/全天"


def _appt_to_dict(a: Appointment) -> dict:
    return {
        "id": a.id,
        "buyer_id": a.buyer_id,
        "exhibitor_id": a.exhibitor_id,
        "exhibition_id": a.exhibition_id,
        "time_slot": a.time_slot or "全天",
        "status": a.status,
        "buyer_name": a.buyer_name or "",
        "exhibitor_name": a.exhibitor_name or "",
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.post("")
def create_appt(
    data: ApptRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    exh = db.query(Exhibition).filter(Exhibition.id == data.exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    exhibitor = db.query(User).filter(User.id == data.exhibitor_id).first()
    if not exhibitor:
        raise NotFound(message="展商不存在")

    appt = Appointment(
        buyer_id=current_user.id,
        exhibitor_id=data.exhibitor_id,
        exhibition_id=data.exhibition_id,
        time_slot=data.time_slot or "全天",
        status="confirmed",
        buyer_name=current_user.nickname or current_user.username,
        exhibitor_name=exhibitor.nickname or exhibitor.username,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    # 通知展商
    notify(db, data.exhibitor_id, "appointment",
           f"📅 {appt.buyer_name} 预约在「{exh.title[:20]}」与你见面",
           f"时段：{appt.time_slot}", f"/exhibitions/{data.exhibition_id}")

    return {"success": True, "code": "OK", "message": "预约成功！展会现场见", "data": _appt_to_dict(appt)}


@router.get("/my")
def my_appts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    if current_user.role == "buyer":
        mine = db.query(Appointment).filter(Appointment.buyer_id == uid).order_by(Appointment.created_at.desc()).all()
    else:
        mine = db.query(Appointment).filter(Appointment.exhibitor_id == uid).order_by(Appointment.created_at.desc()).all()

    # Enrich with names
    items = []
    for a in mine:
        item = _appt_to_dict(a)
        exh = db.query(Exhibition).filter(Exhibition.id == a.exhibition_id).first()
        item["exhibition_title"] = exh.title if exh else ""
        counterpart_id = a.exhibitor_id if current_user.role == "buyer" else a.buyer_id
        u = db.query(User).filter(User.id == counterpart_id).first()
        item["counterpart_name"] = (u.company or u.nickname or u.username) if u else ""
        items.append(item)

    return {"success": True, "code": "OK", "data": {"list": items, "total": len(items)}}
