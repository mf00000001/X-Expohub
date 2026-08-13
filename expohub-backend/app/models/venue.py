"""展馆表（Venue）

展会线下举办的场馆信息:地点、场馆面积、重要信息、荣誉信息(可补充)。
主办方创建展会时可选关联;展会详情可跳转展馆信息页。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Integer, Text, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Venue(Base):
    """展馆表 — 国内常用会展场馆"""
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 基本信息 ----
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True, comment="展馆名称")
    city: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="所在城市")
    address: Mapped[str] = mapped_column(String(300), nullable=False, comment="详细地址")
    area: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="场馆面积(万平方米)"
    )

    # ---- 重要信息 ----
    important_info: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="重要信息(交通/服务/注意事项等)"
    )

    # ---- 荣誉信息(可补充,多条用 JSON 数组字符串) ----
    honors: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="荣誉信息列表(JSON 数组字符串,可补充)"
    )

    # ---- 时间戳 ----
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<Venue(id={self.id}, name={self.name}, city={self.city})>"
