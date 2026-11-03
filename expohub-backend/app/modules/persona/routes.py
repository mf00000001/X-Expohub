"""
画像层只读路由（Persona）

把 `persona.db` 里算好的展会画像吐给前端，供展商/采购商判断"这个展值不值得去"。
**只读**：数据由 `scripts/persona/` 的抓取-抽取-计算流水线产出，接口不提供任何写入口，
否则会出现"页面上改了一个数、下次重算被覆盖、没人知道那份数怎么来的"。

接口：
- GET /api/persona/expos             展会画像列表（品类/城市/档位筛选 + 关键词 + 分页）
- GET /api/persona/expos/{slug}      展会画像详情（含口径、来源、观测溯源）
- GET /api/persona/overview          全局分布与覆盖率（档位直方图 + 字段完整度）
- GET /api/persona/params            标定参数与档位口径（前端解释文案的一致性来源）

## 为什么解释文案要在后端生成

`severe` 这个词在页面上极易被读成"这个展不能去"，但它的真实含义是
"在本样本 43 个可比值里排后 25%"。同理 `unknown` 不是"数据有问题"，
是"这个展没报可比的两个数"。这两句话必须和档位一起下发，
否则前端各写各的解释，一定会有一处写成红牌劝退。

所以每个档位都配 `*_label`（短标题）与 `*_hint`（一句话解释），
取值口径来自 `app.modules.persona.bands.RATIO_CALIBRATION`，
**改档位只改 bands.py，文案跟着版本号走，不在前端硬编码。**

## 口径披露是接口的一部分，不是可选项

观众/展商比的可信度取决于两个数是不是同一个来源。去展网的观众数实测
系统性偏低 20~25%，所以 `scale_source` 必须随数一起下发——
前端要能显示"这组数来自第三方平台，仅供排序参考"。
只给数不给源，等于把校准工作扔给用户。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFound
from app.modules.persona.bands import (
    RATIO_ABS_FLOOR,
    RATIO_BANDS,
    RATIO_CALIBRATION,
)
from app.modules.persona.db import get_persona_db
from app.modules.persona.models import Expo, ExpoObservation, ExpoPersona

router = APIRouter(prefix="/persona", tags=["展会画像"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# ============================================================
# 档位文案 —— 与 bands.py 的常量同源，不在此处另立一套数字
# ============================================================

RATIO_TEXT: dict[str, tuple[str, str]] = {
    "ample": (
        "客源充裕",
        "观众/展商比排在本样本前 25%。注意这是横向排名，不是绝对保证。",
    ),
    "normal": (
        "正常",
        "观众/展商比处于本样本中位区间。",
    ),
    "thin": (
        "偏薄",
        "观众/展商比排在本样本后 25%~50%，每个展位能接触到的买家相对少。",
    ),
    "severe": (
        "摊薄",
        "观众/展商比排在本样本后 25%。注意它**不等于「这个展不能去」**，"
        "只是同类里相对最薄——仍可能是你那个细分品类里最好的选择。",
    ),
    "unknown": (
        "无法判断",
        "这个展没有同时公布观众数和展商数，算不出比值。"
        "缺数据 ≠ 展会不好，只是我们无法从这个维度给结论。",
    ),
}

E4_TEXT: dict[str, tuple[str, str]] = {
    "ample": ("时间充裕", "距开展还有较长时间，报名和备展都来得及。"),
    "normal": ("时间正常", "按常规节奏准备即可。"),
    "urgent": ("偏紧", "备展时间偏紧，建议尽快确认报名与差旅。"),
    "critical": ("紧张", "时间已经很紧，若还没决定要谨慎。"),
    "impossible": ("来不及", "距开展不足 3 天，正常参展流程已来不及。这是唯一一条硬门槛。"),
    "likely_full": ("可能已满", "临近开展，展位可能已经排满，需要直接向主办方确认。"),
    "ongoing": (
        "进行中",
        "展会正在举办，本届展位已无法预订——但如果你是去看展而不是参展，现在正是时候。",
    ),
    "closed": ("已结束", "该届展会已经结束，可关注下一届的档期。"),
    "unknown": ("无法判断", "这个展没有公布开展日期。"),
}

SCALE_SOURCE_TEXT: dict[str, str] = {
    "official": "展会官网/主办方公开数据",
    "qufair": "第三方会展平台（去展网）。实测观众数系统性偏低 20~25%，仅供排序参考",
}


# ============================================================
# 通用小工具
# ============================================================

def _ok(data: Any) -> dict:
    """统一成功响应（与 exhibitions.py / catalog/routes.py 保持一致）"""
    return {"success": True, "code": "OK", "message": "获取成功", "data": data}


def _clean(value: Optional[str]) -> Optional[str]:
    """查询参数归一化：None 或空串/纯空白 → None（不参与筛选）"""
    if value is None:
        return None
    text = value.strip()
    return text or None


def _band_pair(band: Optional[str], table: dict[str, tuple[str, str]]) -> dict:
    """把档位代码翻成 label/hint；未知档位原样透出，不假装认识。"""
    key = band or "unknown"
    label, hint = table.get(key, (key or "unknown", "未归类的档位值，请检查计算脚本。"))
    return {"band": key, "label": label, "hint": hint}


def _latest_persona_join():
    """
    每个展取最新一条计算结果（expo_persona 保留多版本是为了对比参数改动）。

    不用 `DISTINCT ON`——那是 PostgreSQL 专有语法，画像库是 SQLite，会直接编译失败。
    改用 group-by 取 max(id)：id 自增，最新一条就是 max(id)，且比比 computed_at 稳
    （同一批落库时 computed_at 可能是同一个 server_default 时间戳）。
    """
    sub = (
        select(ExpoPersona.expo_id, func.max(ExpoPersona.id).label("pid"))
        .group_by(ExpoPersona.expo_id)
        .subquery()
    )
    return sub


# ============================================================
# 序列化
# ============================================================

def _serialize_card(expo: Expo, p: Optional[ExpoPersona]) -> dict:
    """列表卡片：只放"值不值得去"判断要用到的字段。"""
    ratio = p.visitor_exhibitor_ratio if p else None
    return {
        "slug": expo.slug,
        "name_cn": expo.name_cn,
        "name_en": expo.name_en,
        "city": expo.city,
        "venue_name": expo.venue_name,
        "start_date": expo.start_date,
        "end_date": expo.end_date,
        "edition_no": expo.edition_no,
        "primary_category": expo.primary_category,
        "biz_type": expo.biz_type,
        "audience_access": expo.audience_access,

        # 规模三件套 + 来源（来源必须随数下发，见模块 docstring）
        "visitor_count": expo.visitor_count,
        "visitor_caliber": expo.visitor_caliber,
        "exhibitor_count": expo.exhibitor_count,
        "exhibitor_caliber": expo.exhibitor_caliber,
        "exhibit_area_sqm": expo.exhibit_area_sqm,
        "area_caliber": expo.area_caliber,
        "scale_source": expo.scale_source,
        "scale_source_label": SCALE_SOURCE_TEXT.get(expo.scale_source or "", "来源未标注"),

        # E1 客群可得性
        "e1": {
            "ratio": round(ratio, 1) if ratio is not None else None,
            **_band_pair(p.ratio_band if p else None, RATIO_TEXT),
            "target_lo": p.e1_lo if p else None,
            "target_mid": p.e1_mid if p else None,
            "target_hi": p.e1_hi if p else None,
            "confidence": p.e1_confidence if p else None,
        },

        # E4 展位可得性
        "e4": {
            **_band_pair(p.e4_band if p else None, E4_TEXT),
            "days_left": p.e4_days_left if p else None,
            "deadline": p.e4_deadline if p else None,
        },

        "data_status": expo.data_status,
        "confidence_overall": expo.confidence_overall,
        "computed_at": p.computed_at.isoformat() if p and p.computed_at else None,
    }


# ============================================================
# 路由
# ============================================================

@router.get("/expos", summary="展会画像列表")
def list_expos(
    db: Session = Depends(get_persona_db),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    q: Optional[str] = Query(None, description="关键词，匹配中英文名/城市/展馆"),
    category: Optional[str] = Query(None, description="主品类，见 /persona/params"),
    city: Optional[str] = Query(None, description="举办城市，精确匹配"),
    ratio_band: Optional[str] = Query(None, description="E1 档位：ample/normal/thin/severe/unknown"),
    e4_band: Optional[str] = Query(None, description="E4 档位"),
    scale_source: Optional[str] = Query(None, description="规模数据来源：official/qufair"),
    has_dates: bool = Query(False, description="只要已知开展日期的展"),
    upcoming: bool = Query(
        False,
        description="只要未结束的展（end_date 为空时退化用 start_date）。"
                    "不加这个条件时，已结束的展会按日期排在最前面。",
    ),
    sort: str = Query(
        "start_date",
        description="排序字段：start_date / ratio / name / category",
    ),
    order: str = Query("asc", description="asc / desc"),
):
    """
    展会画像列表。

    默认按开展日升序（最近要开的排前面）——这是用户问"下一个该去哪"时的自然顺序。
    `ratio` 排序会把 `unknown`（比值为 NULL）排到最后，不管 asc/desc，
    因为 NULL 不是 0，让它插在 severe 前面会误导。
    """
    q = _clean(q)
    category = _clean(category)
    city = _clean(city)
    ratio_band = _clean(ratio_band)
    e4_band = _clean(e4_band)
    scale_source = _clean(scale_source)

    # 与最新一条计算结果做 LEFT JOIN：没算过的展也要能列出来（带 unknown）
    latest = _latest_persona_join()
    stmt = select(Expo, ExpoPersona).join(
        latest,
        Expo.id == latest.c.expo_id,
        isouter=True,
    ).join(
        ExpoPersona,
        ExpoPersona.id == latest.c.pid,
        isouter=True,
    )

    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Expo.name_cn.like(like),
            Expo.name_en.like(like),
            Expo.city.like(like),
            Expo.venue_name.like(like),
        ))
    if category:
        stmt = stmt.where(Expo.primary_category == category)
    if city:
        stmt = stmt.where(Expo.city == city)
    if scale_source:
        stmt = stmt.where(Expo.scale_source == scale_source)
    if has_dates:
        stmt = stmt.where(Expo.start_date.is_not(None), Expo.start_date != "")
    if upcoming:
        # ISO 日期串可以直接按字典序比较，不必先转 date。
        # end_date 缺失时退化用 start_date 判断——这是已知偏差（跨多天的展可能被提前算成已结束），
        # 但宁可保守地少列，也不要让用户在列表顶部看到已经闭幕的展。
        today_iso = date.today().isoformat()
        stmt = stmt.where(or_(
            Expo.end_date >= today_iso,
            and_(or_(Expo.end_date.is_(None), Expo.end_date == ""),
                 Expo.start_date >= today_iso),
        ))
    if ratio_band:
        # unknown 同时覆盖"没算过"和"算过但比值为空"两种情况
        if ratio_band == "unknown":
            stmt = stmt.where(or_(
                ExpoPersona.ratio_band.is_(None),
                ExpoPersona.ratio_band == "unknown",
            ))
        else:
            stmt = stmt.where(ExpoPersona.ratio_band == ratio_band)
    if e4_band:
        if e4_band == "unknown":
            stmt = stmt.where(or_(
                ExpoPersona.e4_band.is_(None),
                ExpoPersona.e4_band == "unknown",
            ))
        else:
            stmt = stmt.where(ExpoPersona.e4_band == e4_band)

    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()

    # 排序：NULL 恒排最后，不管 asc/desc。
    # 做法是把"is NULL"作为第一排序键**固定升序**（0=有值在前，1=空值在后），
    # 第二键再按用户指定方向排。如果第一键也跟着 desc，null 会翻到最前面——
    # 那样比值为 NULL 的展会插在 severe 前面，而 NULL 不是 0，会误导。
    sort_map = {
        "start_date": (Expo.start_date.is_(None), Expo.start_date),
        "ratio": (ExpoPersona.visitor_exhibitor_ratio.is_(None),
                  ExpoPersona.visitor_exhibitor_ratio),
        "name": (Expo.name_cn.is_(None), Expo.name_cn),
        "category": (Expo.primary_category.is_(None), Expo.primary_category),
    }
    null_flag, sort_col = sort_map.get(sort, sort_map["start_date"])
    if order.lower() == "desc":
        stmt = stmt.order_by(null_flag.asc(), sort_col.desc(), Expo.id.desc())
    else:
        stmt = stmt.order_by(null_flag.asc(), sort_col.asc(), Expo.id.asc())

    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    items = [_serialize_card(e, p) for e, p in rows]

    return _ok({
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size if total else 0,
        },
    })


@router.get("/expos/{slug}", summary="展会画像详情")
def get_expo(slug: str, db: Session = Depends(get_persona_db)):
    """
    单个展的完整画像。

    比列表多出三块**判断依据**，缺了它们用户没法自己复核结论：
    1. 口径（观众报的是人数还是人次、面积是毛展还是净展）；
    2. 来源（官网一手 vs 第三方平台）；
    3. 观测溯源（这个数是从哪几个页面抄来的）。
    """
    expo = db.execute(select(Expo).where(Expo.slug == slug)).scalar_one_or_none()
    if expo is None:
        raise NotFound(f"未找到展会：{slug}")

    latest = _latest_persona_join()
    p = db.execute(
        select(ExpoPersona)
        .join(latest, ExpoPersona.id == latest.c.pid)
        .where(ExpoPersona.expo_id == expo.id)
    ).scalar_one_or_none()

    # 观测溯源：只取来源类型与数量，正文太长不进接口
    obs_rows = db.execute(
        select(ExpoObservation.source_type, func.count())
        .where(ExpoObservation.expo_id == expo.id)
        .group_by(ExpoObservation.source_type)
    ).all()
    observations = [
        {"source_type": st or "unknown", "count": n} for st, n in obs_rows
    ]

    card = _serialize_card(expo, p)
    card.update({
        "note": p.note if p else None,
        "params_version": p.params_version if p else None,
        "booth_price_standard": expo.booth_price_standard,
        "booth_price_raw": expo.booth_price_raw,
        "booth_deadline": expo.booth_deadline,
        "has_listing": expo.has_listing,
        "listing_completeness": expo.listing_completeness,
        "sample_group": expo.sample_group,
        "observations": observations,
        "calibration": {
            "version": RATIO_CALIBRATION["version"],
            "basis": RATIO_CALIBRATION["basis"],
            "n": RATIO_CALIBRATION["n"],
        },
    })
    return _ok(card)


@router.get("/overview", summary="画像覆盖率与档位分布")
def overview(db: Session = Depends(get_persona_db)):
    """
    全局分布。**覆盖率必须和档位一起给**——
    只报"43 个展算出了比值"而不报分母 94，会让用户以为数据很全。
    """
    total = db.execute(select(func.count(Expo.id))).scalar_one()

    latest = _latest_persona_join()
    ratio_rows = db.execute(
        select(ExpoPersona.ratio_band, func.count())
        .join(latest, ExpoPersona.id == latest.c.pid)
        .group_by(ExpoPersona.ratio_band)
    ).all()
    e4_rows = db.execute(
        select(ExpoPersona.e4_band, func.count())
        .join(latest, ExpoPersona.id == latest.c.pid)
        .group_by(ExpoPersona.e4_band)
    ).all()

    def _dist(rows, table):
        out = {}
        for band, n in rows:
            key = band or "unknown"
            out[key] = {"count": n, "label": table.get(key, (key, ""))[0]}
        # 没算过的展也计入 unknown，否则分布加起来不等于总数
        covered = sum(v["count"] for v in out.values())
        if covered < total:
            out.setdefault("unknown", {"count": 0, "label": RATIO_TEXT["unknown"][0]})
            out["unknown"]["count"] += total - covered
        return out

    def _cov(col):
        n = db.execute(
            select(func.count(Expo.id)).where(col.is_not(None), col != "")
        ).scalar_one()
        return {"filled": n, "total": total, "rate": round(n / total, 3) if total else 0}

    category_rows = db.execute(
        select(Expo.primary_category, func.count())
        .group_by(Expo.primary_category)
        .order_by(func.count().desc())
    ).all()

    return _ok({
        "total_expos": total,
        "e1_distribution": _dist(ratio_rows, RATIO_TEXT),
        "e4_distribution": _dist(e4_rows, E4_TEXT),
        "coverage": {
            "visitor_count": _cov(Expo.visitor_count),
            "exhibitor_count": _cov(Expo.exhibitor_count),
            "exhibit_area_sqm": _cov(Expo.exhibit_area_sqm),
            "start_date": _cov(Expo.start_date),
            "primary_category": _cov(Expo.primary_category),
            "booth_price_standard": _cov(Expo.booth_price_standard),
        },
        "categories": [
            {"category": c or "未分类", "count": n} for c, n in category_rows
        ],
        "calibration": dict(RATIO_CALIBRATION),
    })


@router.get("/params", summary="标定参数与档位口径")
def params():
    """
    前端解释文案的唯一来源。

    档位是**相对排名**，阈值随样本漂移（v2→v3→v4 各重标过一次）。
    把版本号和分位数一起下发，用户才知道"severe"是跟谁比出来的。
    """
    return _ok({
        "calibration": dict(RATIO_CALIBRATION),
        "ratio_bands": [
            {"threshold": th, "band": name,
             "label": RATIO_TEXT[name][0], "hint": RATIO_TEXT[name][1]}
            for th, name in RATIO_BANDS
        ],
        "ratio_abs_floor": {
            "value": RATIO_ABS_FLOOR,
            "hint": "低于此值无条件判 severe，不随样本分位漂移。当前样本不触发，是给脏数据兜底的。",
        },
        "e4_bands": [
            {"band": k, "label": v[0], "hint": v[1]} for k, v in E4_TEXT.items()
        ],
        "scale_sources": [
            {"source": k, "label": v} for k, v in SCALE_SOURCE_TEXT.items()
        ],
    })
