"""RBAC 权限定义 + 角色-权限映射"""

from __future__ import annotations

from enum import Enum
from typing import Any


class Role(str, Enum):
    """用户角色枚举"""
    VISITOR = "visitor"
    EXHIBITOR = "exhibitor"
    BOSS = "boss"
    ORGANIZER = "organizer"


class Permission(str, Enum):
    """权限枚举"""

    # 用户管理
    USER_VIEW = "user:view"
    USER_EDIT = "user:edit"
    USER_MANAGE = "user:manage"

    # 展会管理
    EXHIBITION_LIST = "exhibition:list"
    EXHIBITION_VIEW = "exhibition:view"
    EXHIBITION_CREATE = "exhibition:create"
    EXHIBITION_EDIT = "exhibition:edit"
    EXHIBITION_DELETE = "exhibition:delete"
    EXHIBITION_APPROVE = "exhibition:approve"
    EXHIBITION_PUBLISH = "exhibition:publish"

    # 展位管理
    BOOTH_LIST = "booth:list"
    BOOTH_VIEW = "booth:view"
    BOOTH_BOOK = "booth:book"
    BOOTH_EDIT = "booth:edit"
    BOOTH_CREATE = "booth:create"
    BOOTH_ASSIGN = "booth:assign"

    # 展品管理
    PRODUCT_LIST = "product:list"
    PRODUCT_VIEW = "product:view"
    PRODUCT_CREATE = "product:create"
    PRODUCT_EDIT = "product:edit"
    PRODUCT_DELETE = "product:delete"

    # 采购需求
    PROCUREMENT_CREATE = "procurement:create"
    PROCUREMENT_LIST = "procurement:list"
    PROCUREMENT_VIEW = "procurement:view"
    PROCUREMENT_EDIT = "procurement:edit"
    PROCUREMENT_MATCH = "procurement:match"

    # 报名/收藏
    REGISTRATION_CREATE = "registration:create"
    REGISTRATION_MANAGE = "registration:manage"

    # 消息沟通
    MESSAGE_SEND = "message:send"
    MESSAGE_VIEW = "message:view"

    # 数据统计
    STATS_VIEW_SELF = "stats:view_self"
    STATS_VIEW_GLOBAL = "stats:view_global"
    STATS_EXPORT = "stats:export"

    # 审核管理
    AUDIT_VIEW = "audit:view"
    AUDIT_REVIEW = "audit:review"

    # 团队管理
    TEAM_CREATE = "team:create"
    TEAM_EDIT = "team:edit"
    TEAM_DELETE = "team:delete"
    TEAM_MEMBER_MANAGE = "team:member:manage"

    # 系统配置
    SYSTEM_CONFIG = "system:config"


# 角色-权限映射表
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VISITOR: {
        # 用户
        Permission.USER_VIEW,
        Permission.USER_EDIT,
        # 展会
        Permission.EXHIBITION_LIST,
        Permission.EXHIBITION_VIEW,
        # 展位
        Permission.BOOTH_LIST,
        Permission.BOOTH_VIEW,
        # 展品
        Permission.PRODUCT_LIST,
        Permission.PRODUCT_VIEW,
        # 采购需求
        Permission.PROCUREMENT_CREATE,
        Permission.PROCUREMENT_LIST,
        Permission.PROCUREMENT_VIEW,
        Permission.PROCUREMENT_EDIT,
        # 报名收藏
        Permission.REGISTRATION_CREATE,
        # 消息
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        # 统计
        Permission.STATS_VIEW_SELF,
    },
    Role.EXHIBITOR: {
        # 用户
        Permission.USER_VIEW,
        Permission.USER_EDIT,
        # 展会
        Permission.EXHIBITION_LIST,
        Permission.EXHIBITION_VIEW,
        # 展位
        Permission.BOOTH_LIST,
        Permission.BOOTH_VIEW,
        Permission.BOOTH_BOOK,
        Permission.BOOTH_EDIT,
        # 展品
        Permission.PRODUCT_LIST,
        Permission.PRODUCT_VIEW,
        Permission.PRODUCT_CREATE,
        Permission.PRODUCT_EDIT,
        Permission.PRODUCT_DELETE,
        # 采购需求
        Permission.PROCUREMENT_LIST,
        Permission.PROCUREMENT_VIEW,
        Permission.PROCUREMENT_MATCH,
        # 消息
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        # 统计
        Permission.STATS_VIEW_SELF,
    },
    Role.ORGANIZER: {
        # 用户
        Permission.USER_VIEW,
        Permission.USER_EDIT,
        # 展会
        Permission.EXHIBITION_LIST,
        Permission.EXHIBITION_VIEW,
        Permission.EXHIBITION_CREATE,
        Permission.EXHIBITION_EDIT,
        Permission.EXHIBITION_PUBLISH,
        # 展位
        Permission.BOOTH_LIST,
        Permission.BOOTH_VIEW,
        Permission.BOOTH_CREATE,
        Permission.BOOTH_ASSIGN,
        # 展品
        Permission.PRODUCT_LIST,
        Permission.PRODUCT_VIEW,
        # 采购需求
        Permission.PROCUREMENT_LIST,
        Permission.PROCUREMENT_VIEW,
        # 报名收藏
        Permission.REGISTRATION_MANAGE,
        # 消息
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        # 统计
        Permission.STATS_VIEW_SELF,
        Permission.STATS_VIEW_GLOBAL,
        Permission.STATS_EXPORT,
        # 审核
        Permission.AUDIT_VIEW,
    },
    Role.BOSS: {
        # 用户
        Permission.USER_VIEW,
        Permission.USER_EDIT,
        Permission.USER_MANAGE,
        # 展会
        Permission.EXHIBITION_LIST,
        Permission.EXHIBITION_VIEW,
        Permission.EXHIBITION_APPROVE,
        # 展位
        Permission.BOOTH_LIST,
        Permission.BOOTH_VIEW,
        # 展品
        Permission.PRODUCT_LIST,
        Permission.PRODUCT_VIEW,
        # 采购需求
        Permission.PROCUREMENT_LIST,
        Permission.PROCUREMENT_VIEW,
        # 消息
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        # 统计
        Permission.STATS_VIEW_SELF,
        Permission.STATS_VIEW_GLOBAL,
        Permission.STATS_EXPORT,
        # 审核
        Permission.AUDIT_VIEW,
        Permission.AUDIT_REVIEW,
        # 团队
        Permission.TEAM_CREATE,
        Permission.TEAM_EDIT,
        Permission.TEAM_DELETE,
        Permission.TEAM_MEMBER_MANAGE,
        # 系统
        Permission.SYSTEM_CONFIG,
    },
}


def check_permission(role: Role, permission: Permission) -> bool:
    """
    检查角色是否拥有指定权限

    Args:
        role: 用户角色
        permission: 需要检查的权限

    Returns:
        是否拥有该权限
    """
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_role_permissions(role: Role) -> set[Permission]:
    """
    获取角色拥有的所有权限

    Args:
        role: 用户角色

    Returns:
        权限集合
    """
    return ROLE_PERMISSIONS.get(role, set())
