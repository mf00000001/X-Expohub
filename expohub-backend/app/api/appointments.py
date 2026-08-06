"""V2.9: 展会预约 — 买家约展商线下见面"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.base import get_db
from app.models.user import User
from app.models.exhibition import Exhibition
from app.models.notification import notify
from app.api.deps import get_current_active_user
from app.core.exceptions import NotFound

router = APIRouter(prefix="/appointments", tags=["预约"])

# 简单内存存储
appointments_db = []  # [{id, buyer_id, exhibitor_id, exhibition_id, time_slot, status, created_at}]
_next_id = 1

class ApptRequest(BaseModel):
    exhibitor_id: int
    exhibition_id: int
    time_slot: Optional[str] = None  # "上午/下午/全天"

@router.post("")
def create_appt(data: ApptRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    global _next_id, appointments_db
    exh = db.query(Exhibition).filter(Exhibition.id == data.exhibition_id).first()
    if not exh: raise NotFound(message="展会不存在")
    appt = {"id": _next_id, "buyer_id": current_user.id, "exhibitor_id": data.exhibitor_id,
            "exhibition_id": data.exhibition_id, "time_slot": data.time_slot or "全天",
            "status": "confirmed", "buyer_name": current_user.nickname or current_user.username,
            "created_at": datetime.now(timezone.utc).isoformat()}
    _next_id += 1; appointments_db.append(appt)
    # 通知展商
    notify(db, data.exhibitor_id, "appointment",
           f"📅 {appt['buyer_name']} 预约在「{exh.title[:20]}」与你见面",
           f"时段：{appt['time_slot']}", f"/exhibitions/{data.exhibition_id}")
    return {"success": True, "code": "OK", "message": "预约成功！展会现场见", "data": appt}

@router.get("/my")
def my_appts(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    uid = current_user.id
    if current_user.role == "buyer":
        mine = [a for a in appointments_db if a["buyer_id"] == uid]
    else:
        mine = [a for a in appointments_db if a["exhibitor_id"] == uid]
    # Enrich with names
    for a in mine:
        exh = db.query(Exhibition).filter(Exhibition.id == a["exhibition_id"]).first()
        a["exhibition_title"] = exh.title if exh else ""
        u = db.query(User).filter(User.id == (a["exhibitor_id"] if current_user.role=="buyer" else a["buyer_id"])).first()
        a["counterpart_name"] = (u.company or u.nickname or u.username) if u else ""
    return {"success": True, "code": "OK", "data": {"list": mine, "total": len(mine)}}
