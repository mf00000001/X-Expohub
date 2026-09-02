"""
现场签到路由（P4 新增，前缀 /api/onsite）

- POST  /checkin               单张核销（验签名 + 状态迁移 valid->used + 流水）
- POST  /checkin/batch         批量核销（幂等：重复/已核销逐项跳过）
- POST  /tickets/{ticket_no}/revoke   撤销核销（used->valid + 流水）
- GET   /exhibitions/{id}/stats 到场统计（总数/票种分布/时段曲线/最新流水）

权限：require_permission(ONSITE_MANAGE)（主办方/管理员）
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user, require_permission
from app.core.exceptions import BadRequest, NotFound
from app.core.permissions import Permission
from app.models.base import get_db
from app.models.exhibition import Exhibition
from app.models.user import User
from app.modules.onsite.models import OnsiteCheckinLog
from app.modules.ticketing.models import Ticket
from app.modules.ticketing.routes import _verify_sign

router = APIRouter(prefix="/onsite", tags=["现场签到"])

TICKET_VALID = "valid"
TICKET_USED = "used"


class CheckinRequest(BaseModel):
    exhibition_id: int
    ticket_no: str = Field(..., min_length=6, max_length=40)
    signature: str = Field(..., min_length=8, max_length=64)


class BatchCheckinRequest(BaseModel):
    exhibition_id: int
    items: List[CheckinRequest] = Field(..., min_length=1, max_length=500)


def _verify_exhibition(db: Session, exhibition_id: int) -> Exhibition:
    e = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not e:
        raise NotFound(message="展会不存在")
    return e


def _do_checkin(db: Session, exhibition_id: int, ticket_no: str, signature: str, operator: User) -> dict:
    """单张核销核心逻辑：返回 (ok, reason)；ok=False 不抛异常（供批量用）"""
    ticket = db.query(Ticket).filter(Ticket.ticket_no == ticket_no).first()
    if not ticket:
        return {"ticket_no": ticket_no, "ok": False, "reason": "票券不存在"}
    if ticket.exhibition_id != exhibition_id:
        return {"ticket_no": ticket_no, "ok": False, "reason": "票券不属于该展会"}
    if not _verify_sign(ticket_no, signature):
        return {"ticket_no": ticket_no, "ok": False, "reason": "票券签名校验失败"}
    if ticket.status != TICKET_VALID:
        return {"ticket_no": ticket_no, "ok": False, "reason": f"票券非有效状态({ticket.status})"}

    ticket.status = TICKET_USED
    db.add(OnsiteCheckinLog(
        exhibition_id=exhibition_id, ticket_no=ticket_no,
        ticket_type_name=ticket.ticket_type_name, user_id=ticket.user_id,
        operator_id=operator.id, action="checkin",
    ))
    db.commit()
    return {"ticket_no": ticket_no, "ok": True, "reason": "核销成功"}


@router.post("/checkin")
def checkin(
    data: CheckinRequest,
    db: Session = Depends(get_db),
    operator: User = Depends(require_permission(Permission.ONSITE_MANAGE)),
):
    """单张核销"""
    _verify_exhibition(db, data.exhibition_id)
    result = _do_checkin(db, data.exhibition_id, data.ticket_no, data.signature, operator)
    if not result["ok"]:
        raise BadRequest(message=result["reason"])
    return {"success": True, "code": "OK", "message": "核销成功", "data": result}


@router.post("/checkin/batch")
def batch_checkin(
    data: BatchCheckinRequest,
    db: Session = Depends(get_db),
    operator: User = Depends(require_permission(Permission.ONSITE_MANAGE)),
):
    """批量核销（幂等）：逐项处理，重复票/已核销票跳过不报错"""
    _verify_exhibition(db, data.exhibition_id)
    results = []
    for item in data.items:
        results.append(_do_checkin(db, data.exhibition_id, item.ticket_no, item.signature, operator))
    ok_count = sum(1 for r in results if r["ok"])
    return {"success": True, "code": "OK", "message": f"批量核销完成：成功 {ok_count}/{len(results)}", "data": {
        "success_count": ok_count, "total": len(results), "results": results,
    }}


@router.post("/tickets/{ticket_no}/revoke")
def revoke_checkin(
    ticket_no: str,
    exhibition_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(require_permission(Permission.ONSITE_MANAGE)),
):
    """撤销核销：used -> valid（误核销纠错）"""
    ticket = db.query(Ticket).filter(Ticket.ticket_no == ticket_no).first()
    if not ticket:
        raise NotFound(message="票券不存在")
    if ticket.status != TICKET_USED:
        raise BadRequest(message="仅已核销票可撤销")
    if ticket.exhibition_id != exhibition_id:
        raise BadRequest(message="票券不属于该展会")

    ticket.status = TICKET_VALID
    db.add(OnsiteCheckinLog(
        exhibition_id=exhibition_id, ticket_no=ticket_no,
        ticket_type_name=ticket.ticket_type_name, user_id=ticket.user_id,
        operator_id=operator.id, action="revoke",
    ))
    db.commit()
    return {"success": True, "code": "OK", "message": "已撤销核销，票券恢复有效", "data": {
        "ticket_no": ticket_no, "status": ticket.status,
    }}


@router.get("/exhibitions/{exhibition_id}/stats")
def onsite_stats(
    exhibition_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.ONSITE_MANAGE)),
):
    """到场统计：总核销数/撤销数、票种分布、小时曲线、最新流水"""
    logs = db.query(OnsiteCheckinLog).filter(OnsiteCheckinLog.exhibition_id == exhibition_id).all()
    total = sum(1 for l in logs if l.action == "checkin")
    revoked = sum(1 for l in logs if l.action == "revoke")
    # 票种分布（净到场）
    by_type: dict = {}
    hour_buckets: dict = {}
    for l in logs:
        h = l.created_at.strftime("%Y-%m-%d %H:00") if l.created_at else "?"
        hour_buckets[h] = hour_buckets.get(h, 0) + (1 if l.action == "checkin" else -1)
        if l.action == "checkin":
            by_type[l.ticket_type_name or "未知"] = by_type.get(l.ticket_type_name or "未知", 0) + 1
    return {"success": True, "code": "OK", "message": "获取成功", "data": {
        "exhibition_id": exhibition_id,
        "checkin_count": total,
        "revoke_count": revoked,
        "by_ticket_type": by_type,
        "by_hour": [{"hour": k, "checkin": v} for k, v in sorted(hour_buckets.items())],
        "latest": [
            {"ticket_no": l.ticket_no, "action": l.action,
             "ticket_type_name": l.ticket_type_name,
             "at": l.created_at.isoformat() if l.created_at else None}
            for l in sorted(logs, key=lambda x: x.id or 0, reverse=True)[:10]
        ],
    }}
