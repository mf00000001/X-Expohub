"""审核日志服务（异步版）"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def create_audit_log(
    db: AsyncSession,
    user_id: Optional[int],
    user_role: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """
    创建审计日志

    Args:
        db: 异步数据库会话
        user_id: 操作用户ID
        user_role: 用户角色
        action: 操作类型
        resource_type: 资源类型
        resource_id: 资源ID
        detail: 操作详情
        ip_address: 请求IP
        user_agent: User-Agent

    Returns:
        创建的审计日志对象
    """
    import json

    log = AuditLog(
        user_id=user_id,
        user_role=user_role,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        detail=json.dumps(detail, ensure_ascii=False) if detail else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_audit_logs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[int] = None,
) -> tuple[list[AuditLog], int]:
    """
    获取审计日志列表

    Args:
        db: 异步数据库会话
        page: 页码
        page_size: 每页数量
        action: 操作类型筛选
        resource_type: 资源类型筛选
        user_id: 用户ID筛选

    Returns:
        (日志列表, 总数)
    """
    stmt = select(AuditLog)

    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)

    # count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # paginated
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return list(logs), total
