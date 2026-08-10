"""
ExpoHub 认证与授权模块

功能：
1. 密码哈希与验证（bcrypt）
2. JWT 双令牌机制（Access Token + Refresh Token）
3. RBAC 权限模型（角色-权限映射）
4. 依赖注入式鉴权装饰器
"""

import enum
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Callable, Type

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User, UserRole, UserStatus

# ============================================================
# 密码哈希
# ============================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

security_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希密码是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# JWT 令牌管理
# ============================================================

def create_access_token(
    user_id: int,
    role: str,
    extra_claims: Optional[dict] = None
) -> str:
    """
    创建短期访问令牌（Access Token）

    Args:
        user_id: 用户ID
        role: 用户角色
        extra_claims: 额外声明

    Returns:
        JWT 访问令牌字符串
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user_id: int, role: str) -> str:
    """
    创建长期刷新令牌（Refresh Token）

    Args:
        user_id: 用户ID
        role: 用户角色

    Returns:
        JWT 刷新令牌字符串
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    """
    解码并验证 JWT 令牌

    Args:
        token: JWT 令牌字符串

    Returns:
        解码后的 payload 字典

    Raises:
        HTTPException 401: 令牌无效或已过期
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效的认证令牌: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def refresh_access_token(refresh_token: str) -> dict:
    """
    使用刷新令牌获取新的访问令牌

    Args:
        refresh_token: 刷新令牌

    Returns:
        包含新令牌的字典: {"access_token": str, "token_type": "bearer"}
    """
    payload = decode_token(refresh_token)

    # 验证是刷新令牌
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型错误，请使用刷新令牌",
        )

    user_id = int(payload["sub"])
    role = payload["role"]

    new_access_token = create_access_token(user_id=user_id, role=role)

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


# ============================================================
# RBAC 权限模型
# ============================================================

class Permission(str, enum.Enum):
    """系统权限枚举"""
    # 用户管理
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # 展会管理
    EXHIBITION_CREATE = "exhibition:create"
    EXHIBITION_READ = "exhibition:read"
    EXHIBITION_UPDATE = "exhibition:update"
    EXHIBITION_DELETE = "exhibition:delete"
    EXHIBITION_PUBLISH = "exhibition:publish"
    EXHIBITION_APPROVE = "exhibition:approve"

    # 展位管理
    BOOTH_CREATE = "booth:create"
    BOOTH_READ = "booth:read"
    BOOTH_UPDATE = "booth:update"
    BOOTH_DELETE = "booth:delete"
    BOOTH_BOOK = "booth:book"           # 预订展位
    BOOTH_ASSIGN = "booth:assign"       # 分配展位

    # 报名管理
    REGISTRATION_CREATE = "registration:create"
    REGISTRATION_READ = "registration:read"
    REGISTRATION_CANCEL = "registration:cancel"
    REGISTRATION_CHECKIN = "registration:checkin"

    # 数据分析
    STATS_VIEW = "stats:view"
    STATS_EXPORT = "stats:export"

    # 系统管理
    SYSTEM_CONFIG = "system:config"
    AUDIT_LOG_VIEW = "audit:log:view"
    USER_MANAGE = "user:manage"         # 管理所有用户

    # 采购需求管理
    PROCUREMENT_CREATE = "procurement:create"   # 发布采购需求
    PROCUREMENT_READ = "procurement:read"       # 查看采购需求
    PROCUREMENT_UPDATE = "procurement:update"   # 更新自己的采购需求
    PROCUREMENT_DELETE = "procurement:delete"   # 删除采购需求
    PROCUREMENT_MATCH = "procurement:match"     # 匹配采购需求（展商）

    # 展品管理
    PRODUCT_CREATE = "product:create"           # 创建展品
    PRODUCT_READ = "product:read"               # 查看展品
    PRODUCT_UPDATE = "product:update"           # 更新自己的展品
    PRODUCT_DELETE = "product:delete"           # 删除自己的展品

    # 消息管理
    MESSAGE_SEND = "message:send"               # 发送消息
    MESSAGE_READ = "message:read"               # 查看消息
    MESSAGE_DELETE = "message:delete"           # 删除消息


# ============================================================
# 角色-权限映射表（RBAC 核心）
# ============================================================

ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.VISITOR: {
        # 游客：浏览展会、报名、管理个人信息
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.EXHIBITION_READ,
        Permission.BOOTH_READ,
        Permission.REGISTRATION_CREATE,
        Permission.REGISTRATION_READ,
        Permission.REGISTRATION_CANCEL,
        # 采购需求
        Permission.PROCUREMENT_CREATE,
        Permission.PROCUREMENT_READ,
        Permission.PROCUREMENT_UPDATE,
        Permission.PROCUREMENT_DELETE,
        # 消息
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_READ,
        # 展品（查看）
        Permission.PRODUCT_READ,
    },
    UserRole.EXHIBITOR: {
        # 展商：管理展位、查看展会信息
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.EXHIBITION_READ,
        Permission.BOOTH_READ,
        Permission.BOOTH_BOOK,
        Permission.BOOTH_UPDATE,
        Permission.REGISTRATION_READ,
        Permission.STATS_VIEW,
        # 采购需求（查看和匹配）
        Permission.PROCUREMENT_READ,
        Permission.PROCUREMENT_MATCH,
        # 展品管理
        Permission.PRODUCT_CREATE,
        Permission.PRODUCT_READ,
        Permission.PRODUCT_UPDATE,
        Permission.PRODUCT_DELETE,
        # 消息
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_READ,
    },
    UserRole.ORGANIZER: {
        # 主办方运营：日常展会管理
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.EXHIBITION_CREATE,
        Permission.EXHIBITION_READ,
        Permission.EXHIBITION_UPDATE,
        Permission.EXHIBITION_PUBLISH,
        Permission.BOOTH_CREATE,
        Permission.BOOTH_READ,
        Permission.BOOTH_UPDATE,
        Permission.BOOTH_DELETE,
        Permission.BOOTH_ASSIGN,
        Permission.REGISTRATION_READ,
        Permission.REGISTRATION_CHECKIN,
        Permission.STATS_VIEW,
        Permission.STATS_EXPORT,
        Permission.AUDIT_LOG_VIEW,
        # 采购需求（查看）
        Permission.PROCUREMENT_READ,
        # 展品（查看）
        Permission.PRODUCT_READ,
        # 消息
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_READ,
    },
    UserRole.BOSS: {
        # 老板/高层：全局查看、数据分析、审批
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.EXHIBITION_READ,
        Permission.EXHIBITION_APPROVE,
        Permission.BOOTH_READ,
        Permission.REGISTRATION_READ,
        Permission.STATS_VIEW,
        Permission.STATS_EXPORT,
        Permission.AUDIT_LOG_VIEW,
        Permission.SYSTEM_CONFIG,
        Permission.USER_MANAGE,
        # 采购需求（查看）
        Permission.PROCUREMENT_READ,
        # 展品（查看）
        Permission.PRODUCT_READ,
        # 消息
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_READ,
    },
}


def check_permission(role: UserRole, required_permission: Permission) -> bool:
    """
    检查角色是否拥有指定权限

    Args:
        role: 用户角色
        required_permission: 所需权限

    Returns:
        是否拥有权限
    """
    return required_permission in ROLE_PERMISSIONS.get(role, set())


# ============================================================
# 依赖注入 - 获取当前用户
# ============================================================

class CurrentUser:
    """当前认证用户信息"""
    def __init__(
        self,
        user_id: int,
        username: str,
        role: UserRole,
        status: UserStatus,
        token_payload: dict,
    ):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.status = status
        self.token_payload = token_payload

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    @property
    def is_visitor(self) -> bool:
        return self.role == UserRole.VISITOR

    @property
    def is_exhibitor(self) -> bool:
        return self.role == UserRole.EXHIBITOR

    @property
    def is_organizer(self) -> bool:
        return self.role == UserRole.ORGANIZER

    @property
    def is_boss(self) -> bool:
        return self.role == UserRole.BOSS

    def __repr__(self) -> str:
        return f"<CurrentUser(id={self.user_id}, username='{self.username}', role='{self.role}')>"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[CurrentUser]:
    """
    从请求头中解析 JWT 令牌，返回当前用户信息

    这是可选的依赖注入 - 未登录用户返回 None（游客模式）
    需要强制登录的接口应使用 require_auth 依赖

    Args:
        credentials: HTTP Bearer 令牌
        db: 异步数据库会话

    Returns:
        CurrentUser 或 None（未登录）
    """
    if credentials is None:
        return None

    payload = decode_token(credentials.credentials)

    # 验证是访问令牌
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型错误，请使用访问令牌",
        )

    user_id = int(payload["sub"])
    role_str = payload.get("role", "")

    # 从数据库获取用户信息（异步 select）
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    # 检查用户状态
    if user.status == UserStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )
    if user.status == UserStatus.BANNED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被封禁",
        )

    return CurrentUser(
        user_id=user.id,
        username=user.username,
        role=user.role,
        status=user.status,
        token_payload=payload,
    )


# ============================================================
# 鉴权依赖注入 - 强制登录 + 角色/权限检查
# ============================================================

async def require_auth(
    current_user: Optional[CurrentUser] = Depends(get_current_user),
) -> CurrentUser:
    """
    强制要求用户登录

    Raises:
        HTTPException 401: 未登录
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_role(*roles: UserRole) -> Callable:
    """
    角色检查装饰器 - 要求用户拥有指定角色之一

    用法:
        @router.get("/admin/dashboard")
        async def admin_dashboard(
            current_user: CurrentUser = Depends(require_role(UserRole.ORGANIZER, UserRole.BOSS))
        ):
            ...

    Args:
        roles: 允许的角色列表

    Returns:
        依赖注入函数
    """
    async def role_checker(
        current_user: CurrentUser = Depends(require_auth),
    ) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要以下角色之一: {', '.join(r.value for r in roles)}",
            )
        return current_user
    return role_checker


def require_permission(*permissions: Permission) -> Callable:
    """
    权限检查装饰器 - 要求用户拥有指定权限之一

    用法:
        @router.post("/exhibitions")
        async def create_exhibition(
            current_user: CurrentUser = Depends(require_permission(Permission.EXHIBITION_CREATE))
        ):
            ...

    Args:
        permissions: 所需权限列表（满足其一即可）

    Returns:
        依赖注入函数
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(require_auth),
    ) -> CurrentUser:
        for perm in permissions:
            if check_permission(current_user.role, perm):
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"权限不足，需要以下权限之一: {', '.join(p.value for p in permissions)}",
        )
    return permission_checker


# ============================================================
# 快捷角色依赖注入（常用组合）
# ============================================================

# 仅游客可访问
require_visitor = require_role(UserRole.VISITOR)

# 仅展商可访问
require_exhibitor = require_role(UserRole.EXHIBITOR)

# 仅主办方可访问
require_organizer = require_role(UserRole.ORGANIZER)

# 仅老板可访问
require_boss = require_role(UserRole.BOSS)

# 主办方或老板可访问（管理后台）
require_staff = require_role(UserRole.ORGANIZER, UserRole.BOSS)

# 展商或主办方可访问（参展相关）
require_exhibitor_or_staff = require_role(UserRole.EXHIBITOR, UserRole.ORGANIZER, UserRole.BOSS)

# 任意登录用户可访问
require_any_user = require_role(
    UserRole.VISITOR, UserRole.EXHIBITOR, UserRole.ORGANIZER, UserRole.BOSS
)
