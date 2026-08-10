"""团队管理模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database.session import Base


class Team(Base):
    """团队表"""

    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    boss_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="老板用户ID（团队创建者）")
    name = Column(String(100), nullable=False, comment="团队名称")
    description = Column(String(500), nullable=True, comment="团队描述")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    boss = relationship("User", back_populates="owned_teams", foreign_keys=[boss_id])
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name={self.name})>"


class TeamMember(Base):
    """团队成员表"""

    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True, comment="团队ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="成员用户ID")
    role_in_team = Column(
        Enum("admin", "member", name="team_role"),
        nullable=False,
        default="member",
        comment="团队内角色",
    )
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="加入时间")

    # 关系
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")

    __table_args__ = (
        Index("uk_team_user", "team_id", "user_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<TeamMember(team={self.team_id}, user={self.user_id}, role={self.role_in_team})>"
