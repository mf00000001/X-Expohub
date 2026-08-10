"""展位模型与展品模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Float, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database.session import Base


class Booth(Base):
    """展位表"""

    __tablename__ = "booths"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exhibition_id = Column(Integer, ForeignKey("exhibitions.id"), nullable=False, index=True, comment="所属展会ID")
    exhibitor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True, comment="展商用户ID（空=未分配）")
    booth_number = Column(String(50), nullable=False, comment="展位编号，如 A-001")
    name = Column(String(200), nullable=True, comment="展位名称/标题")
    description = Column(Text, nullable=True, comment="展位描述")
    area = Column(Float, nullable=True, comment="展位面积（㎡）")
    price = Column(Float, nullable=True, comment="展位价格")
    floor = Column(Integer, nullable=True, comment="楼层")
    zone = Column(String(50), nullable=True, comment="展区，如 A区/B区")
    status = Column(
        Enum("available", "reserved", "occupied", "maintenance", name="booth_status"),
        nullable=False,
        default="available",
        index=True,
        comment="展位状态",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    exhibition = relationship("Exhibition", back_populates="booths")
    exhibitor = relationship("User", back_populates="booths", foreign_keys=[exhibitor_id])
    products = relationship("Product", back_populates="booth")

    __table_args__ = (
        Index("idx_exhibition_booth", "exhibition_id", "booth_number", unique=True),
        Index("idx_exhibition_status", "exhibition_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Booth(id={self.id}, number={self.booth_number}, status={self.status})>"


class Product(Base):
    """展品表"""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exhibitor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="展商用户ID")
    booth_id = Column(Integer, ForeignKey("booths.id"), nullable=True, index=True, comment="所属展位ID")
    exhibition_id = Column(Integer, ForeignKey("exhibitions.id"), nullable=True, index=True, comment="所属展会ID（冗余）")
    name = Column(String(200), nullable=False, index=True, comment="展品名称")
    description = Column(Text, nullable=True, comment="展品描述")
    category = Column(String(100), nullable=False, index=True, comment="展品类目")
    images = Column(Text, nullable=True, comment="图片URL列表（JSON数组）")
    price = Column(Float, nullable=True, comment="展品价格")
    specs = Column(Text, nullable=True, comment="规格参数（JSON字符串）")
    status = Column(
        Enum("draft", "published", "offline", name="product_status"),
        nullable=False,
        default="draft",
        index=True,
        comment="展品状态",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 关系
    exhibitor = relationship("User", back_populates="products", foreign_keys=[exhibitor_id])
    booth = relationship("Booth", back_populates="products")
    exhibition = relationship("Exhibition", back_populates="products")

    __table_args__ = (
        Index("idx_exhibitor_status", "exhibitor_id", "status"),
        Index("idx_category_status", "category", "status"),
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name={self.name}, status={self.status})>"
