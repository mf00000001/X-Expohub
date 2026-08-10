"""
ExpoHub 核心数据模型

角色体系：
- visitor:  游客（普通观众，浏览展会）
- buyer:    买家（采购商，注册展会、发布采购需求）
- exhibitor: 展商（参展企业，管理展位）
- boss:     老板（展会主办方高层，查看全局数据）— DEPRECATED，不再使用
- organizer: 主办方（展会运营人员，日常管理）
"""

import enum
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, Integer, DateTime, func, Enum, Boolean,
    Text, ForeignKey, Float, Date, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


# ============================================================
# 枚举定义
# ============================================================

class UserRole(str, enum.Enum):
    """五类角色枚举"""
    VISITOR = "visitor"         # 游客/普通观众
    BUYER = "buyer"             # 买家/采购商
    EXHIBITOR = "exhibitor"     # 展商
    BOSS = "boss"               # @deprecated 已弃用，保留仅为向后兼容。主办方直接发布展会，不再需要老板审批
    ORGANIZER = "organizer"     # 主办方运营人员


class UserStatus(str, enum.Enum):
    """用户状态"""
    PENDING = "pending"         # 待激活
    ACTIVE = "active"           # 已激活
    DISABLED = "disabled"       # 已禁用
    BANNED = "banned"           # 已封禁


class Gender(str, enum.Enum):
    """性别"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    SECRET = "secret"           # 保密


class BoothStatus(str, enum.Enum):
    """展位状态"""
    AVAILABLE = "available"     # 可预订
    RESERVED = "reserved"       # 已预订
    OCCUPIED = "occupied"       # 已占用
    MAINTENANCE = "maintenance" # 维护中


class ExhibitionStatus(str, enum.Enum):
    """展会状态"""
    DRAFT = "draft"             # 草稿
    PENDING = "pending"         # 待审核
    PUBLISHED = "published"     # 已发布
    ONGOING = "ongoing"         # 进行中
    ENDED = "ended"             # 已结束
    CANCELLED = "cancelled"     # 已取消


class ProcurementStatus(str, enum.Enum):
    """采购需求状态"""
    PENDING = "pending"         # 待匹配
    MATCHED = "matched"         # 已匹配
    COMPLETED = "completed"     # 已完成
    CANCELLED = "cancelled"     # 已取消


class ProductStatus(str, enum.Enum):
    """展品状态"""
    DRAFT = "draft"             # 草稿
    PUBLISHED = "published"     # 已发布
    OFFLINE = "offline"         # 已下架


class AuditAction(str, enum.Enum):
    """审计操作类型"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    PUBLISH = "publish"
    CANCEL = "cancel"
    MATCH = "match"
    LOGIN = "login"
    LOGOUT = "logout"


class EnrollmentStatus(str, enum.Enum):
    """展会报名状态（展商/买家报名用）"""
    PENDING = "pending"         # 待审核
    APPROVED = "approved"       # 已通过
    REJECTED = "rejected"       # 已驳回


# ============================================================
# 核心用户表 - 统一用户体系，通过 role 字段区分五类角色
# ============================================================

class User(Base):
    """统一用户表 - 五类角色共用"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 账号信息
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True, comment="邮箱"
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, nullable=True, comment="手机号"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希值"
    )

    # 角色与状态
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), nullable=False, default=UserRole.VISITOR,
        index=True, comment="角色：visitor/buyer/exhibitor/boss(已弃用)/organizer"
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), nullable=False, default=UserStatus.PENDING,
        index=True, comment="用户状态"
    )

    # 个人信息
    nickname: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="昵称"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="头像URL"
    )
    gender: Mapped[Optional[Gender]] = mapped_column(
        Enum(Gender), nullable=True, default=Gender.SECRET, comment="性别"
    )
    company: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="公司/机构名称（展商/买家/主办方用）"
    )
    position: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="职位"
    )
    bio: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="个人简介"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False, comment="更新时间"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后登录时间"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="软删除时间"
    )

    # ========== 关联关系 ==========
    # 游客/买家关联的展会收藏/报名
    visitor_registrations = relationship(
        "VisitorRegistration", back_populates="visitor", lazy="dynamic"
    )
    # 展会报名（展商/买家通用）
    exhibition_enrollments = relationship(
        "ExhibitionEnrollment", back_populates="user", lazy="dynamic"
    )
    # 展商关联的展位
    booths = relationship("Booth", back_populates="exhibitor", lazy="dynamic")
    # 主办方管理的展会
    organized_exhibitions = relationship(
        "Exhibition", back_populates="organizer", lazy="dynamic"
    )
    # 发送的消息
    sent_messages = relationship(
        "Message", foreign_keys="Message.sender_id", back_populates="sender", lazy="dynamic"
    )
    # 接收的消息
    received_messages = relationship(
        "Message", foreign_keys="Message.receiver_id", back_populates="receiver", lazy="dynamic"
    )
    # 提交的评价
    reviews = relationship("Review", back_populates="user", lazy="dynamic")
    # 发布的采购需求
    procurement_requests = relationship(
        "ProcurementRequest", back_populates="visitor", lazy="dynamic"
    )
    # 展商管理的展品
    products = relationship(
        "Product", back_populates="exhibitor", lazy="dynamic"
    )
    # 展商匹配的采购需求
    procurement_matches = relationship(
        "ProcurementMatch", back_populates="exhibitor", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


# ============================================================
# 展会表
# ============================================================

class Exhibition(Base):
    """展会信息表"""
    __tablename__ = "exhibitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True, comment="展会名称"
    )
    short_name: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="展会简称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展会描述"
    )
    cover_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="封面图URL"
    )

    # 时间信息
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="开始时间"
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="结束时间"
    )
    registration_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="报名截止时间"
    )

    # 地点信息
    venue: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="举办场馆"
    )
    address: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="详细地址"
    )
    city: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="城市"
    )

    # 状态与主办方
    status: Mapped[ExhibitionStatus] = mapped_column(
        Enum(ExhibitionStatus), nullable=False, default=ExhibitionStatus.DRAFT,
        index=True, comment="展会状态"
    )
    organizer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="主办方用户ID"
    )

    # 审批信息：主办方创建 → 老板审批 → 发布
    approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="审批人（老板）ID"
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="审批时间"
    )
    reject_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="驳回原因"
    )

    # 统计信息（冗余字段，减少JOIN）
    total_booths: Mapped[int] = mapped_column(
        Integer, default=0, comment="总展位数"
    )
    available_booths: Mapped[int] = mapped_column(
        Integer, default=0, comment="可用展位数"
    )
    visitor_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="报名观众数"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False, comment="更新时间"
    )

    # 关联
    organizer = relationship("User", back_populates="organized_exhibitions")
    booths = relationship("Booth", back_populates="exhibition", lazy="dynamic")
    registrations = relationship(
        "VisitorRegistration", back_populates="exhibition", lazy="dynamic"
    )
    enrollments = relationship(
        "ExhibitionEnrollment", back_populates="exhibition", lazy="dynamic"
    )
    reviews = relationship("Review", back_populates="exhibition", lazy="dynamic")
    products = relationship("Product", back_populates="exhibition", lazy="dynamic")
    procurement_requests = relationship(
        "ProcurementRequest", back_populates="exhibition", lazy="dynamic"
    )

    __table_args__ = (
        Index("ix_exhibitions_city_status", "city", "status"),
        Index("ix_exhibitions_date_range", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<Exhibition(id={self.id}, name='{self.name}')>"


# ============================================================
# 展位表
# ============================================================

class Booth(Base):
    """展位表"""
    __tablename__ = "booths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exhibition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=False, index=True,
        comment="所属展会ID"
    )
    exhibitor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
        comment="展商用户ID（空表示未分配）"
    )

    # 展位信息
    booth_number: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="展位编号，如 A-001"
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="展位名称/标题"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展位描述"
    )
    area: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="展位面积（平方米）"
    )
    price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="展位价格"
    )

    # 位置信息
    floor: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="楼层"
    )
    zone: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="展区，如 A区/B区"
    )

    # 状态
    status: Mapped[BoothStatus] = mapped_column(
        Enum(BoothStatus), nullable=False, default=BoothStatus.AVAILABLE,
        index=True, comment="展位状态"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False, comment="更新时间"
    )

    # 关联
    exhibition = relationship("Exhibition", back_populates="booths")
    exhibitor = relationship("User", back_populates="booths")
    products = relationship("Product", back_populates="booth", lazy="dynamic")

    __table_args__ = (
        UniqueConstraint(
            "exhibition_id", "booth_number",
            name="uq_exhibition_booth_number"
        ),
        Index("ix_booths_exhibition_status", "exhibition_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Booth(id={self.id}, number='{self.booth_number}')>"


# ============================================================
# 展会报名表（展商报名 + 买家注册，统一管理）
# ============================================================

class ExhibitionEnrollment(Base):
    """展会报名表 — 展商报名和买家注册展会"""

    __tablename__ = "exhibition_enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="报名用户ID（展商或买家）"
    )
    exhibition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=False, index=True,
        comment="展会ID"
    )
    # 报名类型: exhibitor(展商报名) / buyer(买家注册)
    enrollment_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="exhibitor",
        comment="报名类型: exhibitor / buyer"
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus), nullable=False, default=EnrollmentStatus.PENDING,
        index=True, comment="审核状态: pending/approved/rejected"
    )
    # 附加信息
    company_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="报名时填写的公司名称"
    )
    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="联系电话"
    )
    remark: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="备注/留言"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="报名时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False, comment="更新时间"
    )

    # 关联
    user = relationship("User", back_populates="exhibition_enrollments")
    exhibition = relationship("Exhibition", back_populates="enrollments")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "exhibition_id", "enrollment_type",
            name="uq_user_exhibition_enrollment"
        ),
        Index("ix_enrollments_exhibition_type", "exhibition_id", "enrollment_type"),
        Index("ix_enrollments_user_type", "user_id", "enrollment_type"),
    )

    def __repr__(self) -> str:
        return f"<ExhibitionEnrollment(user={self.user_id}, exhibition={self.exhibition_id}, type='{self.enrollment_type}')>"


# ============================================================
# 观众报名/收藏表
# ============================================================

class VisitorRegistration(Base):
    """观众报名/收藏展会记录表"""
    __tablename__ = "visitor_registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="游客用户ID"
    )
    exhibition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=False, index=True,
        comment="展会ID"
    )

    # 报名信息
    is_favorite: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否收藏"
    )
    is_registered: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已报名"
    )
    ticket_code: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True, comment="电子票编码"
    )
    check_in_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="签到时间"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False, comment="更新时间"
    )

    # 关联
    visitor = relationship("User", back_populates="visitor_registrations")
    exhibition = relationship("Exhibition", back_populates="registrations")

    __table_args__ = (
        UniqueConstraint(
            "visitor_id", "exhibition_id",
            name="uq_visitor_exhibition"
        ),
        Index("ix_visitor_reg_exhibition", "exhibition_id", "is_registered"),
    )

    def __repr__(self) -> str:
        return f"<VisitorRegistration(visitor={self.visitor_id}, exhibition={self.exhibition_id})>"


# ============================================================
# 操作日志表（审计用）
# ============================================================

class AuditLog(Base):
    """操作审计日志表"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
        comment="操作用户ID"
    )
    user_role: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="用户角色"
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="操作类型"
    )
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="资源类型"
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="资源ID"
    )
    detail: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="操作详情（JSON格式）"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True, comment="请求IP"
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="User-Agent"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="操作时间"
    )

    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}')>"


# ============================================================
# 消息通知表
# ============================================================

class Message(Base):
    """站内消息通知表"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="发送者用户ID"
    )
    receiver_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="接收者用户ID"
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="消息标题"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="消息内容"
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True, comment="是否已读"
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="读取时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="发送时间"
    )

    # 关联
    sender = relationship(
        "User", foreign_keys=[sender_id], back_populates="sent_messages"
    )
    receiver = relationship(
        "User", foreign_keys=[receiver_id], back_populates="received_messages"
    )

    __table_args__ = (
        Index("ix_messages_receiver_read", "receiver_id", "is_read"),
        Index("ix_messages_sender_created", "sender_id", "created_at"),
        Index("ix_messages_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, title='{self.title}', read={self.is_read})>"


# ============================================================
# 展会评价表
# ============================================================

class Review(Base):
    """展会评价表"""
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="评价用户ID"
    )
    exhibition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=False, index=True,
        comment="被评价展会ID"
    )
    rating: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="评分（1-5星）"
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="评价内容"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="评价时间"
    )

    # 关联
    user = relationship("User", back_populates="reviews")
    exhibition = relationship("Exhibition", back_populates="reviews")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "exhibition_id",
            name="uq_user_exhibition_review"
        ),
        Index("ix_reviews_exhibition_rating", "exhibition_id", "rating"),
    )

    def __repr__(self) -> str:
        return f"<Review(id={self.id}, user={self.user_id}, exhibition={self.exhibition_id}, rating={self.rating})>"


# ============================================================
# 采购需求模块 - ProcurementRequest
# ============================================================

class ProcurementRequest(Base):
    """采购需求表 - 买家/游客发布采购需求，展商可匹配"""
    __tablename__ = "procurement_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="发布者（游客/买家）用户ID"
    )
    exhibition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=False, index=True,
        comment="关联展会ID（必填）"
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True, comment="采购标题"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="采购需求详细描述"
    )
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="采购品类"
    )
    budget_min: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="预算下限"
    )
    budget_max: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="预算上限"
    )
    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="采购截止日期"
    )
    status: Mapped[ProcurementStatus] = mapped_column(
        Enum(ProcurementStatus), nullable=False, default=ProcurementStatus.PENDING,
        index=True, comment="状态：pending/matched/completed/cancelled"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False, comment="更新时间"
    )

    # 关联
    visitor = relationship("User", back_populates="procurement_requests")
    exhibition = relationship("Exhibition", back_populates="procurement_requests")
    matches = relationship(
        "ProcurementMatch", back_populates="procurement", lazy="dynamic",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_procurement_status_category", "status", "category"),
        Index("ix_procurement_visitor_status", "visitor_id", "status"),
        Index("ix_procurement_exhibition_status", "exhibition_id", "status"),
        Index("ix_procurement_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ProcurementRequest(id={self.id}, title='{self.title}', status='{self.status}')>"


class ProcurementMatch(Base):
    """采购需求匹配表 - 展商标记匹配采购需求"""
    __tablename__ = "procurement_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    procurement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("procurement_requests.id"), nullable=False, index=True,
        comment="采购需求ID"
    )
    exhibitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="展商用户ID"
    )
    message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展商留言/报价说明"
    )
    quoted_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="报价"
    )
    is_accepted: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="是否被采购方接受（None=待回应）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="匹配时间"
    )

    # 关联
    procurement = relationship("ProcurementRequest", back_populates="matches")
    exhibitor = relationship("User", back_populates="procurement_matches")

    __table_args__ = (
        UniqueConstraint(
            "procurement_id", "exhibitor_id",
            name="uq_procurement_exhibitor"
        ),
        Index("ix_procurement_match_exhibitor", "exhibitor_id"),
    )

    def __repr__(self) -> str:
        return f"<ProcurementMatch(procurement={self.procurement_id}, exhibitor={self.exhibitor_id})>"


# ============================================================
# 展品管理模块 - Product
# ============================================================

class Product(Base):
    """展品表 - 展商管理的展品信息"""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exhibitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
        comment="展商用户ID"
    )
    booth_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("booths.id"), nullable=True, index=True,
        comment="所属展位ID"
    )
    exhibition_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=True, index=True,
        comment="所属展会ID（冗余字段，方便筛选）"
    )

    # 展品基本信息
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True, comment="展品名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展品描述"
    )
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="展品类目"
    )
    images: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展品图片URL列表（JSON数组字符串）"
    )
    price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="展品价格"
    )
    specs: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展品规格参数（JSON字符串）"
    )

    # 状态
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus), nullable=False, default=ProductStatus.DRAFT,
        index=True, comment="状态：draft/published/offline"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False, comment="更新时间"
    )

    # 关联
    exhibitor = relationship("User", back_populates="products")
    booth = relationship("Booth", back_populates="products")
    exhibition = relationship("Exhibition", back_populates="products")

    __table_args__ = (
        Index("ix_products_exhibitor_status", "exhibitor_id", "status"),
        Index("ix_products_category_status", "category", "status"),
        Index("ix_products_exhibition_category", "exhibition_id", "category"),
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name}', status='{self.status}')>"
