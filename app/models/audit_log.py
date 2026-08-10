"""审核日志模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database.session import Base


class AuditLog(Base):
    """审计日志表"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True, comment="操作用户ID")
    user_role = Column(String(20), nullable=True, comment="用户角色")
    action = Column(String(100), nullable=False, index=True, comment="操作类型")
    resource_type = Column(String(50), nullable=False, comment="资源类型")
    resource_id = Column(String(50), nullable=True, comment="资源ID")
    detail = Column(Text, nullable=True, comment="操作详情（JSON）")
    ip_address = Column(String(45), nullable=True, comment="请求IP")
    user_agent = Column(String(500), nullable=True, comment="User-Agent")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="操作时间")

    # 关系
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_user_action", "user_id", "action"),
        Index("idx_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, user={self.user_id}, action={self.action}, resource={self.resource_type})>"
