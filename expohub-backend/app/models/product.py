"""
展品表（Product）

对应前端 API: expo-hub-uniapp/src/api/product.ts

前端 Product 接口字段：
  id, booth_id?, exhibitor_id?, exhibitor_name?,
  name, description, category?, price?, unit?,
  images?, stock?, status,
  created_at?, updated_at?
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, func, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Product(Base):
    """展品表 — 展商管理的展品信息"""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 关联 ----
    booth_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("booths.id"), nullable=True, index=True,
        comment="所属展位 ID"
    )
    micro_booth_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True,
        comment="V2.0: 所属微展位 ID"
    )
    exhibition_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=True, index=True,
        comment="所属展会 ID"
    )
    exhibitor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
        comment="展商用户 ID"
    )
    exhibitor_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="展商名称（冗余）"
    )

    # ---- 展品基本信息 ----
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, index=True, comment="展品名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展品描述"
    )
    name_en: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="展品名称（英文）"
    )
    description_en: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展品描述（英文）"
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True, comment="展品类目"
    )
    price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="展品价格"
    )
    unit: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="单位，如 件/箱/kg"
    )

    # ---- 规格参数（JSON 字符串存储） ----
    specs: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="规格参数（JSON字符串）"
    )

    # ---- 图片（JSON 数组字符串存储） ----
    images: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展品图片 URL 列表（JSON 数组字符串）"
    )

    # ---- 视频 ----
    video_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="展品视频链接（YouTube/Vimeo/MP4）"
    )

    # ---- V2.8: 展品统计 ----
    view_count: Mapped[int] = mapped_column(Integer, default=0, comment="浏览量")
    search_appearances: Mapped[int] = mapped_column(Integer, default=0, comment="搜索曝光量")
    favorite_count: Mapped[int] = mapped_column(Integer, default=0, comment="被收藏数")

    # ---- V2.3: 广交会风格交易信息 ----
    model_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="产品型号"
    )
    material: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="材质"
    )
    min_order: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="最小起订量"
    )
    supply_ability: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="供应能力，如 10000件/月"
    )
    delivery_time: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="交货期，如 15天"
    )
    certifications: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="认证信息，如 CE,FCC,ROHS"
    )
    target_market: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="目标市场，如 欧美/东南亚"
    )

    # ---- 库存 ----
    stock: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="库存数量"
    )

    # ---- 状态 ----
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True,
        comment="状态：draft/published/offline"
    )

    # ---- 时间戳 ----
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
        comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name}')>"
