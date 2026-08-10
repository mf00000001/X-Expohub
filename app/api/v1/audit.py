"""审核 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.dependencies import require_boss, require_staff, require_any_user
from app.database.session import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.dashboard import AuditReviewRequest, AuditSubmitRequest
from app.services.audit_service import create_audit_log, get_audit_logs

router = APIRouter(prefix="/audit", tags=["审核"])


@router.post("/submit", response_model=ApiResponse)
async def submit_audit(
    data: AuditSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_user),
):
    """提交审核请求（任意登录用户）"""
    log = create_audit_log(
        db=db,
        user_id=current_user.id,
        user_role=current_user.role,
        action=f"submit_{data.action}",
        resource_type=data.resource_type,
        resource_id=str(data.resource_id),
        detail={"reason": data.reason} if data.reason else None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return ApiResponse(message="审核请求已提交", data={"audit_id": log.id})


@router.get("/logs", response_model=ApiResponse[PaginatedResponse[dict]])
async def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    action: str = None,
    resource_type: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_staff),
):
    """获取审核日志列表（主办方/老板）"""
    logs, total = get_audit_logs(
        db, page=page, page_size=page_size,
        action=action, resource_type=resource_type,
    )
    total_pages = (total + page_size - 1) // page_size
    return ApiResponse(data=PaginatedResponse(
        items=[
            {
                "id": log.id,
                "user_id": log.user_id,
                "user_role": log.user_role,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ))


@router.get("/pending", response_model=ApiResponse[list[dict]])
async def get_pending_audits(
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """获取待审核列表（老板）"""
    logs, _ = get_audit_logs(db, page=1, page_size=50, action="submit_approve")
    return ApiResponse(data=[
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "detail": log.detail,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ])
