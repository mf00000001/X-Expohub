"""
展会 ↔ 名录展商 参展关系（ExhibitionExhibitor）

为什么单独建这张表
------------------
旧的「弱三层」模型：

    exhibitions  ←(catalog_exhibitors.exhibition_id, 48.8% 有值)  catalog_exhibitors
    catalog_products.exhibitor_id → catalog_exhibitors（100% 有值）

问题有三：
  1. `catalog_exhibitors.exhibition_id` 只有 15,585 / 31,938 有值（2026-10-19 实测），
     展会详情页只能再拿 `expo_name` 字符串别名去硬凑；
  2. 一个展商字段只能挂一个 exhibition_id，**同一展商参加多场 / 多届展会**时会被
     压成一条，另一场就查不到它；
  3. `expo_name` 是名录原文（如 `CMEF 中国国际医疗器械博览会`），与
     `exhibitions.title`（如 `第九十四届中国国际医疗器械博览会（CMEF）`）不保证
     一致，字符串补齐属于补丁。

新模型（干净的多对多）：

    exhibitions 1 ──< exhibition_exhibitors >── 1 catalog_exhibitors ──< catalog_products

- 一行 = 「某展商参加了某届展会」；同一展商参加 N 场就有 N 行；
- `expo_label` 保留名录里的展会原文（可追溯导入来源，不参与任何匹配）；
- `booth_no` 保留**该届**展位号（同一展商换展位不影响其它届）；
- 唯一约束 (exhibition_id, catalog_exhibitor_id)：同一展会同一展商只有一条关系，
  回填脚本用 INSERT OR IGNORE 保证重复执行幂等；
- 两列各自建索引：按展会取展商（详情页主查询）、按展商取参展历史（展商详情页）。

建表脚本：`expohub-backend/scripts/migrate_exhibition_exhibitors.py`（幂等 DDL）。
回填脚本：`expohub-backend/scripts/backfill_exhibition_exhibitors.py`
（expo_name ↔ exhibitions.title 规范化映射，映射不上的不硬塞，只进报告）。

注意：`catalog_exhibitors.exhibition_id` 是本表出现**之前**的遗留对齐列，回填后仍然
保留（不删列、不改数据），但接口层不再读它，避免与新关系表双算。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExhibitionExhibitor(Base):
    """参展关系表（展会 ↔ 名录展商，多对多）"""

    __tablename__ = "exhibition_exhibitors"
    __table_args__ = (
        UniqueConstraint(
            "exhibition_id",
            "catalog_exhibitor_id",
            name="uq_exhibition_exhibitor",
        ),
        # 详情页主查询：WHERE exhibition_id = ? [ORDER BY ...]
        Index("ix_exhibition_exhibitors_exhibition_id", "exhibition_id"),
        # 反向查询（展商参加过哪些届）+ 展品 join
        Index(
            "ix_exhibition_exhibitors_catalog_exhibitor_id",
            "catalog_exhibitor_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    exhibition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("exhibitions.id"),
        nullable=False,
        comment="展会 ID（exhibitions.id）",
    )
    catalog_exhibitor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_exhibitors.id"),
        nullable=False,
        comment="名录展商 ID（catalog_exhibitors.id）",
    )

    # ---- 该届参展信息（名录原文，仅用于展示/追溯，不参与匹配）----
    expo_label: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="名录原文展会名（如 'CMEF 中国国际医疗器械博览会'）",
    )
    booth_no: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="该届展位号（名录原文，可空）",
    )

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return (
            f"<ExhibitionExhibitor(id={self.id}, exhibition_id={self.exhibition_id}, "
            f"catalog_exhibitor_id={self.catalog_exhibitor_id})>"
        )
