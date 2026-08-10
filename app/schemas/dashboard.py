"""数据报表 Schema"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ExhibitionStats(BaseModel):
    """展会统计"""
    total_exhibitions: int = 0
    published_count: int = 0
    ongoing_count: int = 0
    ended_count: int = 0
    draft_count: int = 0
    total_visitors: int = 0
    total_booths: int = 0
    occupied_booths: int = 0
    avg_rating: Optional[float] = None


class ExhibitorStats(BaseModel):
    """展商统计"""
    total_exhibitors: int = 0
    approved_count: int = 0
    pending_count: int = 0
    active_products: int = 0
    total_products: int = 0


class ProcurementStats(BaseModel):
    """采购需求统计"""
    total_requests: int = 0
    pending_count: int = 0
    matched_count: int = 0
    completed_count: int = 0
    total_matches: int = 0


class MessageStats(BaseModel):
    """沟通量统计"""
    total_messages: int = 0
    unread_count: int = 0
    today_count: int = 0


class DashboardResponse(BaseModel):
    """仪表盘数据响应"""
    exhibition_stats: ExhibitionStats
    exhibitor_stats: ExhibitorStats
    procurement_stats: ProcurementStats
    message_stats: MessageStats


class AuditSubmitRequest(BaseModel):
    """提交审核请求"""
    resource_type: str
    resource_id: int
    action: str
    reason: Optional[str] = None


class AuditReviewRequest(BaseModel):
    """审核处理请求"""
    audit_id: int
    action: str  # approve / reject
    reason: Optional[str] = None
