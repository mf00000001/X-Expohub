"""
用户表（User）

五方角色统一用户体系：visitor / buyer / exhibitor / organizer / admin
对应前端 API: expo-hub-uniapp/src/api/auth.ts

注册请求字段：
  username, email, password, role
  (organizer 角色额外需提供 company_name, business_license)

登录请求字段：
  username, password

个人信息响应字段：
  id, username, email, phone, role, status, nickname, avatar_url,
  gender, company, position, bio, company_name, business_license,
  organizer_status, created_at, last_login_at
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """统一用户表 — 通过 role 字段区分五类角色"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 账号信息 (对应 auth.ts register 请求) ----
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True, comment="邮箱"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希值（bcrypt）"
    )

    # ---- 角色与状态 ----
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="visitor", index=True,
        comment="角色：visitor/buyer/exhibitor/organizer/admin"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True,
        comment="状态：pending/active/disabled/banned"
    )

    # ---- 主办方专用字段（仅 organizer 角色有效） ----
    organizer_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default=None, index=True,
        comment="主办方审核状态：pending(待审核)/approved(通过)/rejected(驳回)，仅 organizer 角色使用"
    )
    company_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="主办方公司名称（organizer 角色必填）"
    )
    business_license: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="营业执照图片 URL（organizer 角色必填）"
    )

    # ---- V2.0: 兴趣引导 ----
    interests: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="用户兴趣标签 JSON 数组，如 ['电子及家电','AI/科技']"
    )
    interest_selected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="兴趣选择时间"
    )
    is_onboarded: Mapped[bool] = mapped_column(
        default=False, comment="是否完成新用户引导"
    )

    # ---- V2.2: 商业积分 + 裂变 + 信誉等级 ----
    total_points: Mapped[int] = mapped_column(
        Integer, default=0, comment="商业积分总余额"
    )
    referral_code: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, nullable=True, comment="邀请码"
    )
    referred_by: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="邀请人用户ID"
    )
    exhibitor_tier: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default=None, comment="展商信誉等级：bronze/silver/gold/diamond"
    )

    # ---- V2.0: 展商行业领域 ----
    industry_domain: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="展商所属行业领域，如 '电子及家电'"
    )
    sub_domains: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展商细分领域 JSON 数组"
    )

    # ---- 个人信息 (对应 auth.ts profile) ----
    phone: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, nullable=True, comment="手机号"
    )
    nickname: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="昵称"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="头像 URL"
    )
    gender: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, default="secret",
        comment="性别：male/female/other/secret"
    )
    company: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="公司/机构名称（展商用）"
    )
    position: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="职位"
    )
    bio: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="个人简介"
    )

    # ---- 时间戳 ----
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, comment="注册时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
        nullable=False, comment="更新时间"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最后登录时间"
    )

    @property
    def is_organizer_pending(self) -> bool:
        """主办方是否待审核"""
        return self.role == "organizer" and self.organizer_status == "pending"

    @property
    def is_organizer_approved(self) -> bool:
        """主办方是否已通过审核"""
        return self.role == "organizer" and self.organizer_status == "approved"

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
