"""用户模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Index
from sqlalchemy.orm import relationship

from app.core.constants import Gender, UserStatus
from app.database.session import Base


class User(Base):
    """统一用户表 - 四类角色共用"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    email = Column(String(255), unique=True, nullable=False, index=True, comment="邮箱")
    phone = Column(String(20), unique=True, nullable=True, comment="手机号")
    password_hash = Column(String(255), nullable=False, comment="bcrypt 哈希密码")
    role = Column(
        Enum("visitor", "exhibitor", "boss", "organizer", name="user_role"),
        nullable=False,
        index=True,
        comment="用户角色",
    )
    status = Column(
        Enum("pending", "active", "disabled", "banned", name="user_status"),
        nullable=False,
        default="active",
        index=True,
        comment="用户状态",
    )
    nickname = Column(String(100), nullable=True, comment="昵称")
    avatar_url = Column(String(500), nullable=True, comment="头像URL")
    gender = Column(
        Enum("male", "female", "other", "secret", name="user_gender"),
        nullable=True,
        comment="性别",
    )
    company = Column(String(200), nullable=True, comment="公司名称（展商/主办方必填）")
    position = Column(String(100), nullable=True, comment="职位")
    bio = Column(Text, nullable=True, comment="个人简介")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    deleted_at = Column(DateTime, nullable=True, comment="软删除时间")

    # 关系
    exhibitions = relationship("Exhibition", back_populates="organizer", foreign_keys="Exhibition.organizer_id")
    exhibitor_info = relationship("Exhibitor", back_populates="user", uselist=False)
    booths = relationship("Booth", back_populates="exhibitor", foreign_keys="Booth.exhibitor_id")
    products = relationship("Product", back_populates="exhibitor", foreign_keys="Product.exhibitor_id")
    procurement_requests = relationship("ProcurementRequest", back_populates="visitor")
    sent_messages = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    received_messages = relationship("Message", back_populates="receiver", foreign_keys="Message.receiver_id")
    team_memberships = relationship("TeamMember", back_populates="user")
    owned_teams = relationship("Team", back_populates="boss", foreign_keys="Team.boss_id")
    registrations = relationship("VisitorRegistration", back_populates="visitor")
    reviews = relationship("Review", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        Index("idx_role_status", "role", "status"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
