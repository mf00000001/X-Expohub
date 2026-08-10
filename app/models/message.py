"""消息模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship

from app.database.session import Base


class Message(Base):
    """消息表"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="发送者用户ID")
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="接收者用户ID")
    title = Column(String(200), nullable=False, comment="消息标题")
    content = Column(Text, nullable=False, comment="消息内容")
    is_read = Column(Boolean, default=False, index=True, comment="是否已读")
    read_at = Column(DateTime, nullable=True, comment="读取时间")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="发送时间")

    # 关系
    sender = relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])
    receiver = relationship("User", back_populates="received_messages", foreign_keys=[receiver_id])

    __table_args__ = (
        Index("idx_receiver_read", "receiver_id", "is_read"),
        Index("idx_sender_created", "sender_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, sender={self.sender_id}, receiver={self.receiver_id}, is_read={self.is_read})>"
