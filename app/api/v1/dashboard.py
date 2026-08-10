"""数据报表 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_boss, require_staff
from app.database.session import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.dashboard import (
    AuditReviewRequest,
    AuditSubmitRequest,
    DashboardResponse,
    ExhibitionStats,
    ExhibitorStats,
    MessageStats,
    ProcurementStats,
)
from app.services import dashboard_service
from app.services.audit_service import create_audit_log, get_audit_logs

router = APIRouter(prefix="/dashboard", tags=["数据报表"])


@router.get("/stats", response_model=ApiResponse[DashboardResponse])
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user=Depends(require_staff),
):
    """获取仪表盘统计数据（主办方/老板）"""
    stats = dashboard_service.get_dashboard_stats(db)
    return ApiResponse(data=stats)


@router.get("/stats/exhibitions", response_model=ApiResponse[ExhibitionStats])
async def get_exhibition_stats(
    db: Session = Depends(get_db),
    current_user=Depends(require_staff),
):
    """获取展会统计（主办方/老板）"""
    stats = dashboard_service.get_exhibition_stats(db)
    return ApiResponse(data=stats)


@router.get("/stats/exhibitors", response_model=ApiResponse[ExhibitorStats])
async def get_exhibitor_stats(
    db: Session = Depends(get_db),
    current_user=Depends(require_staff),
):
    """获取展商统计（主办方/老板）"""
    stats = dashboard_service.get_exhibitor_stats(db)
    return ApiResponse(data=stats)


@router.get("/stats/procurements", response_model=ApiResponse[ProcurementStats])
async def get_procurement_stats(
    db: Session = Depends(get_db),
    current_user=Depends(require_staff),
):
    """获取采购需求统计（主办方/老板）"""
    stats = dashboard_service.get_procurement_stats(db)
    return ApiResponse(data=stats)


@router.get("/stats/messages", response_model=ApiResponse[MessageStats])
async def get_message_stats(
    db: Session = Depends(get_db),
    current_user=Depends(require_staff),
):
    """获取消息统计（主办方/老板）"""
    stats = dashboard_service.get_message_stats(db)
    return ApiResponse(data=stats)
