"""V2.4: 通知API"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.base import get_db
from app.models.user import User
from app.models.notification import Notification
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/notifications", tags=["通知"])


@router.get("")
def list_notifications(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    total = q.count()
    items = q.order_by(Notification.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    unread = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id, Notification.is_read == False
    ).scalar() or 0
    return {
        "success": True, "code": "OK",
        "data": {
            "list": [{"id": i.id, "type": i.type, "title": i.title, "content": i.content,
                       "link": i.link, "is_read": i.is_read,
                       "created_at": i.created_at.isoformat() if i.created_at else None} for i in items],
            "total": total, "unread": unread, "page": page, "pageSize": page_size,
        }
    }


@router.get("/unread-count")
def unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id, Notification.is_read == False
    ).scalar() or 0
    return {"success": True, "code": "OK", "data": {"count": count}}


@router.post("/{nid}/read")
def mark_read(nid: int, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == nid, Notification.user_id == current_user.id).first()
    if n: n.is_read = True; db.commit()
    return {"success": True, "code": "OK"}


@router.post("/read-all")
def mark_all_read(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == current_user.id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"success": True, "code": "OK"}
