"""
全局枚举常量定义

包含用户角色、状态、展会状态等所有业务枚举。
"""

from __future__ import annotations

from enum import Enum


class RoleEnum(str, Enum):
    """用户角色枚举（两方撮合模型：展商 ↔ 采购商，展会由平台自营）

    2026-10-19 决策：取消 organizer（会展举办方）角色，展会创建与运营能力收归 admin。
    迁移脚本 scripts/migrate_drop_organizer.py 会把存量 organizer 账号升级为 admin。
    """
    VISITOR = "visitor"         # 游客/观众（浏览展会、搜索展商）
    BUYER = "buyer"             # 买家（发布采购需求、在线沟通）
    EXHIBITOR = "exhibitor"     # 展商（卖方）
    ADMIN = "admin"             # 平台管理员（含展会自营：创建展会/展位/票务/核销）

    @classmethod
    def values(cls) -> list[str]:
        return [m.value for m in cls]


# 平台自营展会的展示名（2026-10-19 取消主办方角色后，展会统一由平台运营）
PLATFORM_OPERATOR_NAME = "平台运营"


class UserStatusEnum(str, Enum):
    """用户状态枚举"""
    PENDING = "pending"       # 待审核
    ACTIVE = "active"         # 正常
    DISABLED = "disabled"     # 禁用
    BANNED = "banned"         # 封禁


class ExhibitionStatusEnum(str, Enum):
    """展会状态枚举"""
    DRAFT = "draft"           # 草稿
    PENDING = "pending"       # 待审批
    PUBLISHED = "published"   # 已发布
    ONGOING = "ongoing"       # 进行中
    ENDED = "ended"           # 已结束
    CANCELLED = "cancelled"   # 已取消


class BoothStatusEnum(str, Enum):
    """展位状态枚举"""
    AVAILABLE = "available"       # 可预订
    RESERVED = "reserved"         # 已预订
    OCCUPIED = "occupied"         # 已占用
    MAINTENANCE = "maintenance"   # 维护中


class ProductStatusEnum(str, Enum):
    """展品状态枚举"""
    DRAFT = "draft"           # 草稿
    PUBLISHED = "published"   # 已发布
    OFFLINE = "offline"       # 已下架


class ProcurementStatusEnum(str, Enum):
    """采购需求状态枚举"""
    PENDING = "pending"       # 待匹配
    MATCHED = "matched"       # 已匹配
    COMPLETED = "completed"   # 已完成
    CANCELLED = "cancelled"   # 已取消


class ExhibitorStatusEnum(str, Enum):
    """展商审核状态枚举"""
    PENDING = "pending"       # 待审核
    APPROVED = "approved"     # 已通过
    REJECTED = "rejected"     # 已驳回


class TeamRoleEnum(str, Enum):
    """团队角色枚举"""
    ADMIN = "admin"           # 管理员
    MEMBER = "member"         # 普通成员


class GenderEnum(str, Enum):
    """性别枚举"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    SECRET = "secret"


class MembershipTierEnum(str, Enum):
    """V2.0: 微展位会员等级"""
    FREE = "free"             # 免费：1-3个展品
    REGULAR = "regular"       # 普通：1-8个展品
    FLAGSHIP = "flagship"     # 旗舰：无限展品


class GameTaskTypeEnum(str, Enum):
    """V2.3: 展商养成任务类型"""
    COMPLETE_PROFILE = "complete_profile"
    UPLOAD_PRODUCTS = "upload_products"
    GET_VIEWS = "get_views"
    GET_FAVORITES = "get_favorites"
    GET_MATCH = "get_match"


class PointsTransactionTypeEnum(str, Enum):
    """V2.2: 积分交易类型"""
    EARN_BROWSE = "earn_browse"
    EARN_PROCUREMENT = "earn_procurement"
    EARN_BOOKING = "earn_booking"
    EARN_REGISTRATION = "earn_registration"
    REDEEM_VIP = "redeem_vip"
    REDEEM_LUNCH = "redeem_lunch"
    REDEEM_GIFT = "redeem_gift"
