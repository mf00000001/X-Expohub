"""展会评价模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database.session import Base


class Review(Base):
    """展会评价表"""

    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="评价用户ID")
    exhibition_id = Column(Integer, ForeignKey("exhibitions.id"), nullable=False, index=True, comment="被评价展会ID")
    rating = Column(Integer, nullable=False, comment="评分（1-5星）")
    content = Column(Text, nullable=True, comment="评价内容")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="评价时间")

    # 关系
    user = relationship("User", back_populates="reviews")
    exhibition = relationship("Exhibition", back_populates="reviews")

    __table_args__ = (
        Index("uk_user_exhibition_review", "user_id", "exhibition_id", unique=True),
        Index("idx_exhibition_rating", "exhibition_id", "rating"),
    )

    def __repr__(self) -> str:
        return f"<Review(id={self.id}, user={self.user_id}, exhibition={self.exhibition_id}, rating={self.rating})>"
