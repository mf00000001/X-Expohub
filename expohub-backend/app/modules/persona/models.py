"""
画像库表结构（100 展规模）

设计要点：
- **数值字段必须带口径**。观众数分人次/人数/注册数，展商数分企业/品牌/展位，
  面积分净/毛。只存整数不存口径，100 个展算出的分位全是幻觉。
- **观测与主值分离**。expo 存"当前采信值"（便于计算和人工核对），
  expo_observation 存每一次采集的原文（便于交叉验证和溯源）。
- **名录完整度必填**。展商列表常只放 30%，不记 completeness 会让 E2 系统性低估。
- **不引主库外键**。source_exhibition_id 只是逻辑关联。

对应文档：docs/展会画像-采集字段清单.md / 展会画像-维度清单.md(v0.4)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.persona.db import PersonaBase


class Expo(PersonaBase):
    """
    展会主档（一个展会一行，目标 100 行）

    宽表放"解析后的采信值"，供 E1–E6 直接计算；原始观测在 ExpoObservation。
    """

    __tablename__ = "expo"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- 身份 ----
    # 归一化名称（去空格/全半角/别名），用于去重，勿手改
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    # 主库 exhibitions.id，逻辑关联（无外键，跨库不成立）
    source_exhibition_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    name_cn: Mapped[str] = mapped_column(String(200), nullable=False, comment="展会名称（中）")
    name_en: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="展会名称（英）")

    # ---- L0/L1 基本盘 ----
    city: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True, comment="举办城市")
    venue_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, comment="展馆名称")
    start_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True, comment="开始日期 ISO")
    end_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, comment="结束日期 ISO")
    edition_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="届次，第 N 届")
    biz_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="b2b / b2c / mixed / unknown"
    )
    audience_access: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="trade_only / public / mixed / unknown（L0 硬门槛）"
    )

    # ---- 品类（E1/E2 前置）----
    primary_category: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True, comment="主品类，取值见 app.models.category.EXHIBITION_CATEGORIES"
    )
    # 多品类 + 权重：[{"name": "电子及家电", "weight": 0.7}, ...]
    categories_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="多品类及权重 JSON")

    # ---- 规模（E1 核心，**必须有口径**）----
    visitor_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="观众数（已折算为人数）")
    visitor_caliber: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="person / visit / registered / unknown"
    )
    visitor_count_raw: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, comment="观众数原文")
    exhibitor_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="展商数")
    exhibitor_caliber: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="company / brand / booth / unknown"
    )
    exhibit_area_sqm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="展览面积 ㎡")
    area_caliber: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="net / gross / unknown"
    )

    # ---- 价格与时间窗（E3/E4）----
    booth_price_standard: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="标摊价 元/9㎡（取最低档）"
    )
    booth_price_raw: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="价格原文")
    booth_deadline: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, comment="展位报名截止日 ISO")

    # ---- 名录（E2）----
    has_listing: Mapped[bool] = mapped_column(default=False, comment="是否抓到展商名录")
    listing_completeness: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="full / partial / sponsor_only / none —— 缺此项 E2 不可用"
    )

    # ---- 管理与抽样 ----
    sample_group: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        index=True,
        comment="core_head/core_mid/core_new/boundary/comprehensive —— 用于核查 18×4 分层结构",
    )
    data_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True,
        comment="draft / pending_verify / verified / excluded（三源冲突进 pending_verify，不进计算集）"
    )
    confidence_overall: Mapped[Optional[str]] = mapped_column(
        String(5), nullable=True, comment="high / mid / low"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ExpoObservation(PersonaBase):
    """
    字段级原始观测（每次采集一条，多来源并存）

    作用是回答"这个数从哪来、口径是什么、和别的来源冲突吗"。
    同一 expo + field_key 允许多条（官网一份、展后报告一份），
    由计算层按 confidence 排序取最优。
    """

    __tablename__ = "expo_observation"
    __table_args__ = (
        UniqueConstraint("expo_id", "field_key", "source_url", name="uq_obs_expo_field_src"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    expo_id: Mapped[int] = mapped_column(ForeignKey("expo.id", ondelete="CASCADE"), index=True)

    field_key: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True,
        comment="visitor_count / exhibitor_count / booth_price / area / deadline ..."
    )
    raw_text: Mapped[Optional[str]] = mapped_column(String(300), nullable=True, comment="页面原文")
    num_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="解析后数值")
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="人次/人/家/㎡/元")
    caliber: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, comment="口径说明")

    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="official / post_report / press / thirdparty / manual"
    )
    fetched_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, comment="抓取时间 ISO")
    confidence: Mapped[Optional[str]] = mapped_column(
        String(5), nullable=True, comment="high / mid / low（按来源类型与是否交叉验证推）"
    )

    batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("import_batch.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ExpoExhibitor(PersonaBase):
    """
    展商名录（E2 唯一数据来源）

    注意：企业名 + 展位号才能算"位置系数"；只有企业名时 E2 只能算竞品数量。
    """

    __tablename__ = "expo_exhibitor"
    __table_args__ = (
        UniqueConstraint("expo_id", "company_name", "booth_no", name="uq_exh_expo_company_booth"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    expo_id: Mapped[int] = mapped_column(ForeignKey("expo.id", ondelete="CASCADE"), index=True)

    company_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    booth_no: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, comment="展位号，无则空")
    zone: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, comment="展区/分馆")
    country: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    category_tag: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="企业品类标签，映射到 18 品类"
    )

    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    fetched_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("import_batch.id"), nullable=True)


class ExpoPhase(PersonaBase):
    """
    分期展的期次（广交会这类：一个展 3 期，各期日期/展区不同）

    为什么必须单独一张表：`expo.start_date/end_date` 只有一对，装不下
    "10-15~19 / 10-23~27 / 10-31~11-04"。批次 1 当时只能塞进一期，
    另外两期静默丢失，而表面上看还是"有日期"的——展商报第二期，
    系统给的却是第一期档期，这种错比空值危险得多。
    """

    __tablename__ = "expo_phase"
    __table_args__ = (UniqueConstraint("expo_id", "phase_no", name="uq_phase_expo_no"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    expo_id: Mapped[int] = mapped_column(ForeignKey("expo.id", ondelete="CASCADE"), index=True)

    phase_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="第几期，如 1/2/3")
    phase_name: Mapped[Optional[str]] = mapped_column(
        String(80), nullable=True, comment="期次名，如「先进制造」「品质家居」"
    )
    start_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    zone_hint: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True, comment="该期展区/展馆提示"
    )
    evidence: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ExpoHistory(PersonaBase):
    """往届数据（上届规模、售罄日），用于 E4 推断与复展率"""

    __tablename__ = "expo_history"
    __table_args__ = (UniqueConstraint("expo_id", "edition_year", name="uq_hist_expo_year"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    expo_id: Mapped[int] = mapped_column(ForeignKey("expo.id", ondelete="CASCADE"), index=True)

    edition_year: Mapped[int] = mapped_column(Integer, nullable=False, comment="年份，如 2026")
    visitor_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exhibitor_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    area_sqm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sold_out_days_before: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="上届展位售罄日距开展的天数"
    )
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)


class ExpoPersona(PersonaBase):
    """
    计算结果快照（可重算，不是数据源）

    保留多次计算是为了对比"参数改了以后结果怎么变"——
    这是校准 3 个参数时唯一可用的回归依据。
    """

    __tablename__ = "expo_persona"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    expo_id: Mapped[int] = mapped_column(ForeignKey("expo.id", ondelete="CASCADE"), index=True)

    params_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # E1
    visitor_exhibitor_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ratio_band: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, comment="ample / normal / thin / severe"
    )
    e1_lo: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    e1_mid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    e1_hi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    e1_confidence: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)

    # E4
    e4_band: Mapped[Optional[str]] = mapped_column(
        String(12), nullable=True, comment="ample / normal / urgent / closed / likely_full"
    )
    e4_days_left: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    e4_deadline: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PersonaParam(PersonaBase):
    """
    可调参数（全系统只有 3 个，见维度清单 10.8）

    版本化存放，便于"改参数 → 重算 → 对比排序变化"。
    """

    __tablename__ = "persona_param"
    __table_args__ = (UniqueConstraint("key", "version", name="uq_param_key_version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    value_json: Mapped[str] = mapped_column(Text, nullable=False, comment="参数值 JSON")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ImportBatch(PersonaBase):
    """导入批次（CSV 每批一条），用于回滚与追责"""

    __tablename__ = "import_batch"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    operator: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


ALL_TABLES = [
    Expo,
    ExpoObservation,
    ExpoExhibitor,
    ExpoHistory,
    ExpoPersona,
    PersonaParam,
    ImportBatch,
]
