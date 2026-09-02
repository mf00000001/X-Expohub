"""
RBAC 权限模型

定义 Role / Permission 枚举及角色-权限映射表。
权限控制粒度分为三层：路由层 → 角色层 → 权限层。
"""

from __future__ import annotations

from enum import Enum

from app.core.constants import RoleEnum


class Permission(str, Enum):
    """系统权限枚举

    命名规范：{resource}:{operation}
    - resource: 资源类型（user / exhibition / booth / product 等）
    - operation: 操作类型（create / view / edit / delete / approve 等）
    """

    # ---- 票务管理 ----
    TICKET_MANAGE = "ticket:manage"        # 票种/票务管理（主办方/管理员）
    # ---- 现场签到 ----
    ONSITE_MANAGE = "onsite:manage"        # 现场核销/撤销/统计（主办方/管理员）
    # ---- 平台运营 ----
    PLATFORM_MANAGE = "platform:manage"    # 平台运营（计费档位/导入/总览，仅管理员）

    # ---- 用户管理 ----
    USER_VIEW = "user:view"           # 查看个人信息
    USER_EDIT = "user:edit"           # 编辑个人信息
    USER_MANAGE = "user:manage"       # 管理用户（管理员）

    # ---- 展会管理 ----
    EXHIBITION_LIST = "exhibition:list"       # 浏览展会列表
    EXHIBITION_VIEW = "exhibition:view"       # 查看展会详情
    EXHIBITION_CREATE = "exhibition:create"   # 创建展会
    EXHIBITION_EDIT = "exhibition:edit"       # 编辑展会
    EXHIBITION_DELETE = "exhibition:delete"   # 删除展会
    EXHIBITION_APPROVE = "exhibition:approve" # 审批展会
    EXHIBITION_PUBLISH = "exhibition:publish" # 发布展会

    # ---- 展位管理 ----
    BOOTH_LIST = "booth:list"         # 浏览展位
    BOOTH_VIEW = "booth:view"         # 查看展位详情
    BOOTH_BOOK = "booth:book"         # 预订展位
    BOOTH_EDIT = "booth:edit"         # 编辑展位信息
    BOOTH_CREATE = "booth:create"     # 创建展位
    BOOTH_ASSIGN = "booth:assign"     # 分配展位
    BOOTH_APPROVE = "booth:approve"   # 审核展商入驻

    # ---- 展品管理 ----
    PRODUCT_LIST = "product:list"     # 浏览展品
    PRODUCT_VIEW = "product:view"     # 查看展品详情
    PRODUCT_CREATE = "product:create" # 发布展品
    PRODUCT_EDIT = "product:edit"     # 编辑展品
    PRODUCT_DELETE = "product:delete" # 删除展品

    # ---- 采购需求 ----
    PROCUREMENT_CREATE = "procurement:create"   # 发布采购
    PROCUREMENT_LIST = "procurement:list"       # 浏览采购需求
    PROCUREMENT_VIEW = "procurement:view"       # 查看采购详情
    PROCUREMENT_EDIT = "procurement:edit"       # 编辑采购需求
    PROCUREMENT_DELETE = "procurement:delete"   # 删除采购需求
    PROCUREMENT_MATCH = "procurement:match"     # 匹配采购

    # ---- 消息沟通 ----
    MESSAGE_SEND = "message:send"     # 发送消息
    MESSAGE_VIEW = "message:view"     # 查看消息

    # ---- 数据统计 ----
    STATS_VIEW_SELF = "stats:view_self"       # 查看个人统计
    STATS_VIEW_GLOBAL = "stats:view_global"   # 查看全局统计
    STATS_EXPORT = "stats:export"             # 导出数据报表

    # ---- 审核管理 ----
    AUDIT_VIEW = "audit:view"         # 查看审核日志
    AUDIT_REVIEW = "audit:review"     # 执行审核操作
    AUDIT_ORGANIZER = "audit:organizer"  # 审核主办方入驻

    # ---- 团队管理 ----
    TEAM_CREATE = "team:create"       # 创建团队
    TEAM_EDIT = "team:edit"           # 编辑团队
    TEAM_DELETE = "team:delete"       # 删除团队
    TEAM_MEMBER_MANAGE = "team:member:manage"  # 管理成员

    # ---- 系统配置 ----
    SYSTEM_CONFIG = "system:config"   # 系统配置


# ============================================================
# 角色-权限映射表
# ============================================================

ROLE_PERMISSIONS: dict[RoleEnum, set[Permission]] = {
    # ---- 游客 (visitor)：浏览展会、搜索展商 ----
    RoleEnum.VISITOR: {
        Permission.USER_VIEW,
        Permission.USER_EDIT,
        Permission.EXHIBITION_LIST,
        Permission.EXHIBITION_VIEW,
        Permission.BOOTH_LIST,
        Permission.BOOTH_VIEW,
        Permission.PRODUCT_LIST,
        Permission.PRODUCT_VIEW,
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        Permission.STATS_VIEW_SELF,
    },

    # ---- 买家 (buyer)：发布采购需求、在线沟通 ----
    RoleEnum.BUYER: {
        Permission.USER_VIEW,
        Permission.USER_EDIT,
        Permission.EXHIBITION_LIST,
        Permission.EXHIBITION_VIEW,
        Permission.BOOTH_LIST,
        Permission.BOOTH_VIEW,
        Permission.PRODUCT_LIST,
        Permission.PRODUCT_VIEW,
        Permission.PROCUREMENT_CREATE,
        Permission.PROCUREMENT_LIST,
        Permission.PROCUREMENT_VIEW,
        Permission.PROCUREMENT_EDIT,
        Permission.PROCUREMENT_DELETE,
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        Permission.STATS_VIEW_SELF,
    },

    # ---- 展商 (exhibitor) ----
    RoleEnum.EXHIBITOR: {
        Permission.USER_VIEW,
        Permission.USER_EDIT,
        Permission.EXHIBITION_LIST,
        Permission.EXHIBITION_VIEW,
        Permission.BOOTH_LIST,
        Permission.BOOTH_VIEW,
        Permission.BOOTH_BOOK,
        Permission.BOOTH_EDIT,
        Permission.PRODUCT_LIST,
        Permission.PRODUCT_VIEW,
        Permission.PRODUCT_CREATE,
        Permission.PRODUCT_EDIT,
        Permission.PRODUCT_DELETE,
        Permission.PROCUREMENT_LIST,
        Permission.PROCUREMENT_VIEW,
        Permission.PROCUREMENT_MATCH,
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        Permission.STATS_VIEW_SELF,
    },

    # ---- 主办方 (organizer) ----
    RoleEnum.ORGANIZER: {
        Permission.USER_VIEW,
        Permission.USER_EDIT,
        Permission.EXHIBITION_LIST,
        Permission.EXHIBITION_VIEW,
        Permission.EXHIBITION_CREATE,
        Permission.EXHIBITION_EDIT,
        Permission.EXHIBITION_DELETE,
        Permission.EXHIBITION_PUBLISH,
        Permission.BOOTH_LIST,
        Permission.BOOTH_VIEW,
        Permission.BOOTH_CREATE,
        Permission.BOOTH_ASSIGN,
        Permission.BOOTH_APPROVE,
        Permission.PRODUCT_LIST,
        Permission.PRODUCT_VIEW,
        Permission.PROCUREMENT_LIST,
        Permission.PROCUREMENT_VIEW,
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        Permission.STATS_VIEW_SELF,
        Permission.STATS_VIEW_GLOBAL,
        Permission.STATS_EXPORT,
        Permission.AUDIT_VIEW,
        Permission.TICKET_MANAGE,
        Permission.ONSITE_MANAGE,
    },

    # ---- 平台管理员 (admin)：审核主办方 + 全局管理 ----
    RoleEnum.ADMIN: {
        Permission.USER_VIEW,
        Permission.USER_EDIT,
        Permission.USER_MANAGE,
        Permission.EXHIBITION_LIST,
        Permission.EXHIBITION_VIEW,
        Permission.EXHIBITION_CREATE,
        Permission.EXHIBITION_EDIT,
        Permission.EXHIBITION_DELETE,
        Permission.EXHIBITION_APPROVE,
        Permission.EXHIBITION_PUBLISH,
        Permission.BOOTH_LIST,
        Permission.BOOTH_VIEW,
        Permission.BOOTH_BOOK,
        Permission.BOOTH_EDIT,
        Permission.BOOTH_CREATE,
        Permission.BOOTH_ASSIGN,
        Permission.BOOTH_APPROVE,
        Permission.PRODUCT_LIST,
        Permission.PRODUCT_VIEW,
        Permission.PRODUCT_CREATE,
        Permission.PRODUCT_EDIT,
        Permission.PRODUCT_DELETE,
        Permission.PROCUREMENT_LIST,
        Permission.PROCUREMENT_VIEW,
        Permission.PROCUREMENT_CREATE,
        Permission.PROCUREMENT_EDIT,
        Permission.PROCUREMENT_DELETE,
        Permission.PROCUREMENT_MATCH,
        Permission.MESSAGE_SEND,
        Permission.MESSAGE_VIEW,
        Permission.STATS_VIEW_SELF,
        Permission.STATS_VIEW_GLOBAL,
        Permission.STATS_EXPORT,
        Permission.AUDIT_VIEW,
        Permission.AUDIT_REVIEW,
        Permission.AUDIT_ORGANIZER,
        Permission.TEAM_CREATE,
        Permission.TEAM_EDIT,
        Permission.TEAM_DELETE,
        Permission.TEAM_MEMBER_MANAGE,
        Permission.SYSTEM_CONFIG,
        Permission.TICKET_MANAGE,
        Permission.ONSITE_MANAGE,
        Permission.PLATFORM_MANAGE,
    },
}


def get_role_permissions(role: RoleEnum) -> set[Permission]:
    """获取指定角色的所有权限

    Args:
        role: 用户角色

    Returns:
        该角色拥有的权限集合
    """
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: RoleEnum, permission: Permission) -> bool:
    """检查角色是否拥有指定权限

    Args:
        role: 用户角色
        permission: 待检查的权限

    Returns:
        拥有返回 True，否则 False
    """
    return permission in ROLE_PERMISSIONS.get(role, set())
