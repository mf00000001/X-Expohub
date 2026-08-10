"""全局常量定义"""

from __future__ import annotations

from enum import Enum


class UserStatus(str, Enum):
    """用户状态"""
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"
    BANNED = "banned"


class ExhibitionStatus(str, Enum):
    """展会状态"""
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    ONGOING = "ongoing"
    ENDED = "ended"
    CANCELLED = "cancelled"


class BoothStatus(str, Enum):
    """展位状态"""
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class ProductStatus(str, Enum):
    """展品状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    OFFLINE = "offline"


class ProcurementStatus(str, Enum):
    """采购需求状态"""
    PENDING = "pending"
    MATCHED = "matched"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TeamRole(str, Enum):
    """团队角色"""
    ADMIN = "admin"
    MEMBER = "member"


class Gender(str, Enum):
    """性别"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    SECRET = "secret"
