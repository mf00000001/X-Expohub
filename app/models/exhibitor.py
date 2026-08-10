"""展商信息模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database.session import Base


class Exhibitor(Base):
    """展商扩展信息表"""

    __tablename__ = "exhibitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True, comment="用户ID")
    company_name = Column(String(200), nullable=False, comment="公司全称")
    company_short_name = Column(String(50), nullable=True, comment="公司简称")
    logo_url = Column(String(500), nullable=True, comment="公司Logo")
    business_scope = Column(Text, nullable=True, comment="经营范围")
    website = Column(String(200), nullable=True, comment="公司官网")
    contact_name = Column(String(50), nullable=True, comment="联系人姓名")
    contact_phone = Column(String(20), nullable=True, comment="联系人电话")
    contact_email = Column(String(255), nullable=True, comment="联系人邮箱")
    qualification_files = Column(Text, nullable=True, comment="资质文件（JSON数组）")
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="审核状态: pending/approved/rejected",
    )
    verified_at = Column(DateTime, nullable=True, comment="审核通过时间")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    user = relationship("User", back_populates="exhibitor_info")

    def __repr__(self) -> str:
        return f"<Exhibitor(id={self.id}, company={self.company_name}, status={self.status})>"
