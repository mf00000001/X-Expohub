"""采购需求模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Float, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship

from app.database.session import Base


class ProcurementRequest(Base):
    """采购需求表"""

    __tablename__ = "procurement_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    visitor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="发布者（游客）用户ID")
    title = Column(String(200), nullable=False, index=True, comment="采购标题")
    description = Column(Text, nullable=True, comment="需求详细描述")
    category = Column(String(100), nullable=False, index=True, comment="采购品类")
    budget_min = Column(Float, nullable=True, comment="预算下限")
    budget_max = Column(Float, nullable=True, comment="预算上限")
    deadline = Column(DateTime, nullable=True, comment="采购截止日期")
    status = Column(
        Enum("pending", "matched", "completed", "cancelled", name="procurement_status"),
        nullable=False,
        default="pending",
        index=True,
        comment="需求状态",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    visitor = relationship("User", back_populates="procurement_requests")
    matches = relationship("ProcurementMatch", back_populates="procurement_request")

    __table_args__ = (
        Index("idx_visitor_status", "visitor_id", "status"),
        Index("idx_status_category", "status", "category"),
    )

    def __repr__(self) -> str:
        return f"<ProcurementRequest(id={self.id}, title={self.title}, status={self.status})>"


class ProcurementMatch(Base):
    """采购需求匹配表"""

    __tablename__ = "procurement_matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    procurement_id = Column(Integer, ForeignKey("procurement_requests.id"), nullable=False, index=True, comment="采购需求ID")
    exhibitor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="展商用户ID")
    message = Column(Text, nullable=True, comment="展商留言/报价说明")
    quoted_price = Column(Float, nullable=True, comment="报价")
    is_accepted = Column(Boolean, nullable=True, comment="是否被采购方接受（NULL=待回应）")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="匹配时间")

    # 关系
    procurement_request = relationship("ProcurementRequest", back_populates="matches")
    exhibitor = relationship("User", foreign_keys=[exhibitor_id])

    __table_args__ = (
        Index("uk_procurement_exhibitor", "procurement_id", "exhibitor_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ProcurementMatch(id={self.id}, procurement={self.procurement_id}, exhibitor={self.exhibitor_id})>"
