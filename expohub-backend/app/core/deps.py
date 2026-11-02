"""
API 依赖注入

提供：
- get_current_user: 从 Bearer Token 中解析当前用户
- get_current_active_user: 要求用户状态为 active
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_token, hash_password, verify_password
from app.core.exceptions import Unauthorized, Forbidden
from app.core.constants import RoleEnum
from app.core.permissions import Permission, has_permission
from app.models.base import get_db
from app.models.user import User


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization Header 解析当前登录用户

    Args:
        authorization: Bearer <token>
        db: 数据库会话

    Returns:
        当前登录的 User 对象

    Raises:
        Unauthorized: 未提供 token 或 token 无效
    """
    if not authorization:
        raise Unauthorized(message="请先登录")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized(message="认证格式错误，需要 Bearer Token")

    try:
        payload = verify_token(token)
    except ValueError as e:
        raise Unauthorized(message=str(e))

    # 验证 token 类型
    if payload.get("type") != "access":
        raise Unauthorized(message="请使用 Access Token")

    user_id = payload.get("sub")
    if not user_id:
        raise Unauthorized(message="令牌无效：缺少用户标识")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise Unauthorized(message="用户不存在或已被删除")

    # V3.2: 令牌版本校验(登出后旧 token 立即失效)
    if payload.get("ver") != (user.token_version or 0):
        raise Unauthorized(message="令牌已失效，请重新登录")

    # 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求用户状态为 active

    Args:
        current_user: 当前用户

    Returns:
        当前活跃用户

    Raises:
        Forbidden: 用户状态不是 active
    """
    if current_user.status != "active":
        raise Forbidden(message="账号已被禁用或待审核，请联系管理员")
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """要求当前用户为平台管理员

    Args:
        current_user: 当前活跃用户

    Returns:
        平台管理员用户

    Raises:
        Forbidden: 非管理员角色
    """
    if current_user.role != "admin":
        raise Forbidden(message="仅平台管理员可执行此操作")
    return current_user


def require_permission(permission: Permission):
    """统一 RBAC 权限依赖（基于 ROLE_PERMISSIONS 声明表）

    用法:
        current_user: User = Depends(require_permission(Permission.PRODUCT_CREATE))

    注意: 该依赖只校验"角色是否拥有该权限"，资源归属校验仍需在路由内完成
    （例如编辑展会时校验 exh.organizer_id == current_user.id 或 admin 放行）。
    """
    async def _checker(current_user: User = Depends(get_current_active_user)) -> User:
        # 防御性加固：role 来自数据库，可能存在历史残留值（如已下线的 organizer）
        # 或其它非法值。RoleEnum(...) 解析失败时降级为“拒绝访问”（403），
        # 而不是让 ValueError 冒泡成 500。只包住解析这一句，权限判定逻辑不变。
        try:
            role = RoleEnum(current_user.role)
        except (ValueError, TypeError):
            raise Forbidden(message="账号角色无效，请联系平台管理员")
        if not has_permission(role, permission):
            raise Forbidden(message="权限不足，无法执行此操作")
        return current_user
    return _checker
