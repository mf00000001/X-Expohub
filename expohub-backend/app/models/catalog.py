"""
展商名录 / 展品库模型（Catalog）

数据来源：**第三方公开名录导入**（信息快照，约 3.1 万展商 / 7 万展品），
不是平台账号，也不与 `users(role=exhibitor)` / `products`（展商自己上传的展品）
混用，因此单独建表。

设计口径（务必与导入脚本 / app/modules/catalog/routes.py 保持一致）：
- 两张表都是**只读**快照：接口层不提供任何写操作；
- 不加 relationship：列表/详情全部用显式列查询 + 批量 IN 查询，
  避免隐式懒加载导致 N+1（3 万 + 7 万行规模下这是硬要求）；
- 除 `name` 与 `product_count` 外一律可空：名录是外部数据，字段缺失很常见，
  缺字段应当入库而不是让导入脚本炸掉；
- 唯一键按"展会 + 展商名"、"展会 + 展商名 + 展品名"去重，配合导入脚本的
  INSERT OR IGNORE / ON CONFLICT 保证重复导入幂等。

建表脚本：`expohub-backend/scripts/migrate_catalog_tables.py`（幂等 DDL）。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CatalogExhibitor(Base):
    """名录展商（第三方公开名录快照，非平台账号）"""

    __tablename__ = "catalog_exhibitors"
    __table_args__ = (
        UniqueConstraint("expo_name", "name", name="uq_catalog_exhibitor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 名称 ----
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, comment="展商名称（原文）"
    )
    name_en: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="展商名称（英文/别名）"
    )

    # ---- 所属展会 ----
    expo_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True,
        comment="展会名称（名录原文，与 exhibitions.title 不保证一致）"
    )
    exhibition_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("exhibitions.id"), nullable=True, index=True,
        comment="人工/脚本对齐到的展会 ID（可空，未对齐时为 NULL）"
    )

    # ---- 分类维度（列表筛选 + facets 用）----
    industry: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True, comment="行业"
    )
    city: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True, comment="城市"
    )
    country: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="国家/地区"
    )

    # ---- 参展信息 ----
    booth_no: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="展位号"
    )
    company_type: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="企业类型，如 制造商/贸易商"
    )
    scale: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="企业规模，如 100-500人"
    )
    main_business: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="主营产品/业务（大字段，列表查询不取）"
    )
    website: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="官网/主页链接"
    )

    # ---- 统计 ----
    product_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0"),
        comment="名录内展品数（导入时算好，列表排序用，避免每次 COUNT）"
    )

    # ---- 长文本 ----
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="展商简介（大字段，列表查询不取）"
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="数据来源标识（第三方名录名称/批次）"
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
        return f"<CatalogExhibitor(id={self.id}, name='{self.name}')>"


class CatalogProduct(Base):
    """名录展品（第三方公开名录快照，非展商上传的 products）"""

    __tablename__ = "catalog_products"
    __table_args__ = (
        UniqueConstraint(
            "expo_name", "exhibitor_name", "name", name="uq_catalog_product"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 展品基本信息 ----
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, comment="展品名称"
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True, comment="展品类目"
    )
    application: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="应用领域/用途"
    )
    price_spec: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="价格/规格（名录原文，非结构化）"
    )
    image: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="主图 URL"
    )
    detail_html: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="详情 HTML（大字段，列表查询不取）"
    )

    # ---- 归属展商（冗余名称 + 可空外键）----
    exhibitor_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True, comment="展商名称（冗余，与名录原文一致）"
    )
    exhibitor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("catalog_exhibitors.id"), nullable=True, index=True,
        comment="关联 catalog_exhibitors.id（可空：展商未导入/未能匹配时为 NULL）"
    )
    expo_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True, comment="展会名称（名录原文）"
    )
    booth_no: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="展位号"
    )

    source: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="数据来源标识（第三方名录名称/批次）"
    )

    # ---- 时间戳 ----
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )

    def __repr__(self) -> str:
        return f"<CatalogProduct(id={self.id}, name='{self.name}')>"
