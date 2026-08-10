"""观众报名/收藏模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship

from app.database.session import Base


class VisitorRegistration(Base):
    """观众报名/收藏表"""

    __tablename__ = "visitor_registrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    visitor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="游客用户ID")
    exhibition_id = Column(Integer, ForeignKey("exhibitions.id"), nullable=False, index=True, comment="展会ID")
    is_favorite = Column(Boolean, default=False, comment="是否收藏")
    is_registered = Column(Boolean, default=False, comment="是否已报名")
    ticket_code = Column(String(100), unique=True, nullable=True, comment="电子票编码")
    check_in_at = Column(DateTime, nullable=True, comment="签到时间")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    visitor = relationship("User", back_populates="registrations")
    exhibition = relationship("Exhibition", back_populates="registrations")

    __table_args__ = (
        Index("uk_visitor_exhibition", "visitor_id", "exhibition_id", unique=True),
        Index("idx_exhibition_registered", "exhibition_id", "is_registered"),
    )

    def __repr__(self) -> str:
        return f"<VisitorRegistration(visitor={self.visitor_id}, exhibition={self.exhibition_id})>"
