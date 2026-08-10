"""展会模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Float, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database.session import Base


class Exhibition(Base):
    """展会表"""

    __tablename__ = "exhibitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True, comment="展会名称")
    short_name = Column(String(50), nullable=True, comment="展会简称")
    description = Column(Text, nullable=True, comment="展会描述")
    cover_url = Column(String(500), nullable=True, comment="封面图URL")
    start_date = Column(DateTime, nullable=False, comment="开始时间")
    end_date = Column(DateTime, nullable=False, comment="结束时间")
    registration_deadline = Column(DateTime, nullable=True, comment="报名截止时间")
    venue = Column(String(200), nullable=False, comment="举办场馆")
    address = Column(String(500), nullable=False, comment="详细地址")
    city = Column(String(100), nullable=False, index=True, comment="城市")
    status = Column(
        Enum("draft", "pending", "published", "ongoing", "ended", "cancelled", name="exhibition_status"),
        nullable=False,
        default="draft",
        index=True,
        comment="展会状态",
    )
    organizer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="主办方用户ID")
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="审批人（老板）ID")
    approved_at = Column(DateTime, nullable=True, comment="审批时间")
    reject_reason = Column(Text, nullable=True, comment="驳回原因")
    total_booths = Column(Integer, default=0, comment="总展位数（冗余）")
    available_booths = Column(Integer, default=0, comment="可用展位数（冗余）")
    visitor_count = Column(Integer, default=0, comment="报名观众数（冗余）")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    organizer = relationship("User", back_populates="exhibitions", foreign_keys=[organizer_id])
    approver = relationship("User", foreign_keys=[approved_by])
    booths = relationship("Booth", back_populates="exhibition")
    products = relationship("Product", back_populates="exhibition")
    registrations = relationship("VisitorRegistration", back_populates="exhibition")
    reviews = relationship("Review", back_populates="exhibition")

    __table_args__ = (
        Index("idx_city_status", "city", "status"),
        Index("idx_date_range", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<Exhibition(id={self.id}, name={self.name}, status={self.status})>"
