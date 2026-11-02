"""
展会路由（Exhibitions）

端点：
- GET    /exhibitions                  展会列表
- GET    /exhibitions/registrations    我的报名列表（必须在 :id 之前）
- GET    /exhibitions/:id/stats        该展会真实聚合（展商/展品/城市/行业）
- GET    /exhibitions/:id/exhibitors   该展会参展展商（名录优先）
- GET    /exhibitions/:id/products     该展会名录展品
- GET    /exhibitions/:id              展会详情
- POST   /exhibitions                  创建展会
- PUT    /exhibitions/:id              更新展会
- DELETE /exhibitions/:id              删除展会
- POST   /exhibitions/:id/register     报名参展
- DELETE /exhibitions/:id/register     取消报名
- POST   /exhibitions/:id/approve      审批展会
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.core.config import settings
from app.core.constants import PLATFORM_OPERATOR_NAME
from app.core.exceptions import NotFound, BadRequest, Forbidden, Unauthorized
from app.models.base import get_db
from app.models.user import User
from app.models.exhibition import Exhibition
from app.models.venue import Venue
from app.models.booth import Booth
from app.models.catalog import CatalogExhibitor, CatalogProduct
from app.models.exhibition_exhibitor import ExhibitionExhibitor
from app.models.micro_booth import MicroBooth
from app.models.product import Product
from app.core.deps import get_current_active_user, get_current_user

router = APIRouter(prefix="/exhibitions", tags=["展会"])


# ============================================================
# 公开可见口径 + 可选登录依赖
# ============================================================
#
# 公开可见 = status 不在 ('draft', 'cancelled') 里（草稿与已取消不对外）。
# 这个口径必须与 analytics/public_stats.py 的 PUBLIC_HIDDEN_EXHIBITION_STATUS
# 完全一致，否则首页数字与公开列表 total 会打架（实测曾出现 4 vs 5）。
HIDDEN_EXHIBITION_STATUS = ("draft", "cancelled")

# 可选登录用的 Bearer 提取器：auto_error=False —— 不带 token 时不报 401
_bearer_optional = HTTPBearer(auto_error=False)


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """可选登录依赖：有有效 token 返回用户，否则返回 None（不抛 401）。

    为什么不用 deps.get_current_active_user：那会强制登录，游客就打不开
    公开的展会列表了。这里没有去改 deps.py，只在 token 存在时复用
    get_current_user 的完整校验（令牌类型 / 令牌版本 / 用户是否存在），
    校验失败一律按游客处理（不暴露"token 过期"之类的 401，避免公开页被登出）。

    Returns:
        当前活跃用户；游客 / token 无效 / 账号被禁用 → None
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        user = await get_current_user(
            authorization=f"{credentials.scheme} {credentials.credentials}",
            db=db,
        )
    except (Unauthorized, Forbidden):
        return None
    # 账号被禁用/待审核的，按游客处理（不给看草稿）
    if user.status != "active":
        return None
    return user


# ============================================================
# 日期校验（创建 / 编辑共用）
# ============================================================
#
# 背景：此前创建/编辑接口对 start_date / end_date 完全不校验，库里因此混进过
# '0123-12-03'（年份 123）这类脏数据并出现在公开列表。这里补上入库前的校验，
# 但**只做格式与区间校验，不自动判断/清理任何历史数据**（参见 STATE.md 教训：
# 曾用"年份不在 2000-2100 就当垃圾删"的启发式误删真实展会）。

# 展会日期允许的年份区间（含端点）
_YEAR_MIN = 2000
_YEAR_MAX = 2100

# 报文（对外错误提示，保持中文提示语稳定）
_MSG_BAD_DATE_FORMAT = "日期格式不正确"
_MSG_YEAR_OUT_OF_RANGE = f"日期年份需在 {_YEAR_MIN}-{_YEAR_MAX} 之间"
_MSG_END_BEFORE_START = "结束日期不能早于开始日期"


def _parse_exhibition_date(value: str, field_label: str) -> datetime:
    """把展会日期字符串解析成 datetime，失败抛 400「日期格式不正确」。

    支持两种写法（其余一律拒绝）：
      1. 纯日期  ``YYYY-MM-DD``                例如 2026-11-10
      2. ISO 时间 ``YYYY-MM-DDTHH:MM:SS±TZ``    例如 2026-11-10T09:00:00+08:00
         （也接受以 Z 结尾的 UTC 写法，如 2026-11-10T01:00:00Z）

    Args:
        value: 待解析的日期字符串
        field_label: 字段名，仅用于错误提示定位（如 start_date）

    Raises:
        BadRequest: 400，报文「日期格式不正确」
    """
    text = (value or "").strip()
    if not text:
        raise BadRequest(message=_MSG_BAD_DATE_FORMAT, detail={"field": field_label})

    parsed: Optional[datetime] = None
    # 规则一：YYYY-MM-DD 纯日期
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        parsed = None
    # 规则二：ISO 8601 时间（带 T 与时区）
    if parsed is None and "T" in text.upper():
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            parsed = None
    if parsed is None:
        raise BadRequest(message=_MSG_BAD_DATE_FORMAT, detail={"field": field_label})

    # 规则三：年份必须落在 2000-2100 之间
    if not (_YEAR_MIN <= parsed.year <= _YEAR_MAX):
        raise BadRequest(message=_MSG_YEAR_OUT_OF_RANGE, detail={"field": field_label})

    return parsed


def _validate_exhibition_dates(
    start_date: Optional[str],
    end_date: Optional[str],
    *,
    existing_start: Optional[str] = None,
    existing_end: Optional[str] = None,
) -> None:
    """校验展会的开始/结束日期，不合法直接抛 400。

    - 创建：传 start_date / end_date，两者都必须给且合法。
    - 编辑：只校验本次提交的字段（未提交的沿用库内值做先后比较，见 existing_*）。

    规则：
      1. start_date、end_date 必须能解析（YYYY-MM-DD 或 ISO）；
      2. 年份在 2000-2100 之间；
      3. start_date <= end_date。

    Raises:
        BadRequest: 400
    """
    start_dt = _parse_exhibition_date(start_date, "start_date") if start_date is not None else None
    end_dt = _parse_exhibition_date(end_date, "end_date") if end_date is not None else None

    # 编辑场景：本次没改的那一侧用库内旧值参与先后比较。
    # 旧值可能是历史脏数据（如 '0123-12-03'），此时无法解析——不阻断本次修改，
    # 但也不做先后比较（用户改另一侧时应同时提交合法值）。
    if start_dt is None and existing_start:
        try:
            start_dt = _parse_exhibition_date(existing_start, "start_date")
        except BadRequest:
            start_dt = None
    if end_dt is None and existing_end:
        try:
            end_dt = _parse_exhibition_date(existing_end, "end_date")
        except BadRequest:
            end_dt = None

    # 规则四：结束日期不能早于开始日期
    if start_dt is not None and end_dt is not None:
        # 一侧带时区、一侧不带时无法直接比较，统一去掉时区后再比先后
        if start_dt.tzinfo is not None and end_dt.tzinfo is not None:
            start_cmp, end_cmp = start_dt, end_dt
        else:
            start_cmp, end_cmp = start_dt.replace(tzinfo=None), end_dt.replace(tzinfo=None)
        if start_cmp > end_cmp:
            raise BadRequest(
                message=_MSG_END_BEFORE_START,
                detail={"start_date": start_date or existing_start,
                        "end_date": end_date or existing_end},
            )


# ============================================================
# Pydantic Schemas
# ============================================================

class ExhibitionCreate(BaseModel):
    """创建展会请求"""
    title: str
    description: Optional[str] = None
    cover_image: Optional[str] = None
    start_date: str
    end_date: str
    location: str
    venue_id: Optional[int] = None  # V3.1: 关联展馆(可选)
    status: Optional[str] = "draft"


class ExhibitionUpdate(BaseModel):
    """更新展会请求（所有字段可选）"""
    title: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    venue_id: Optional[int] = None  # V3.2: 关联展馆(可改)
    status: Optional[str] = None


class ExhibitionApproveRequest(BaseModel):
    """审批展会请求"""
    approved: bool = True
    comment: Optional[str] = None


def _exhibitor_count_map(db: Optional[Session], exhibition_ids) -> dict:
    """批量算每个展会的「参展展商数」（列表 / 详情共用，避免逐行查库）。

    计数口径（2026-10-19 修正「列表显示 0 家、点进去 13,306 家」）：

    1. **优先参展关系表** `exhibition_exhibitors`：一条 GROUP BY 出本页所有展会的
       展商数；唯一约束 `(exhibition_id, catalog_exhibitor_id)` 保证同一展商在同一
       展会只有一条关系，COUNT 天然去重，不用 DISTINCT；
    2. 该展会在关系表里**一行关系都没有**时，回落到原 `booths` 口径
       （已占用展位按 `exhibitor_id` 去重）—— 平台自建展会仍能显示展商数；
    3. 两者都没有 → 0（不会因为库没数据而报错）。

    为什么要批量：`_exhibition_to_dict` 逐行调用，一页 20 条会产生 40 条 COUNT；
    这里固定 2 条查询（关系表 + 缺失展会的 booths 回落），与页大小无关。

    Args:
        db: 会话；为 None 时返回空 map（调用方按 0 处理）
        exhibition_ids: 本页展会 id 列表（可含 None / 重复，内部会清理）

    Returns:
        {exhibition_id: 展商数}
    """
    if db is None:
        return {}
    ids = sorted({int(i) for i in (exhibition_ids or []) if i is not None})
    if not ids:
        return {}

    # 1) 关系表（主口径）
    rows = (
        db.query(ExhibitionExhibitor.exhibition_id, func.count(ExhibitionExhibitor.id))
        .filter(ExhibitionExhibitor.exhibition_id.in_(ids))
        .group_by(ExhibitionExhibitor.exhibition_id)
        .all()
    )
    counts = {int(exhibition_id): int(cnt or 0) for exhibition_id, cnt in rows}

    # 2) 关系表没有的展会 → 回落 booths（同一条 SQL 批量取）
    missing = [i for i in ids if i not in counts]
    if missing:
        booth_rows = (
            db.query(
                Booth.exhibition_id,
                func.count(func.distinct(Booth.exhibitor_id)),
            )
            .filter(
                Booth.exhibition_id.in_(missing),
                Booth.exhibitor_id.isnot(None),
            )
            .group_by(Booth.exhibition_id)
            .all()
        )
        counts.update({int(exhibition_id): int(cnt or 0) for exhibition_id, cnt in booth_rows})

    return {i: counts.get(i, 0) for i in ids}


def _exhibition_to_dict(
    exh: Exhibition,
    db: Optional[Session] = None,
    exhibitor_count: Optional[int] = None,
) -> dict:
    """将 Exhibition 模型转为前端响应格式

    Args:
        exh: 展会实体
        db: 会话（取场馆信息 / 单个展会算展商数时必需）
        exhibitor_count: 已算好的展商数（列表接口用 `_exhibitor_count_map` 批量算后
            传入，避免逐行 COUNT）；不传时按 `_exhibitor_count_map` 单场口径现算
    """
    venue_info = None
    if exh.venue_id is not None and db is not None:
        v = db.query(Venue).filter(Venue.id == exh.venue_id).first()
        if v:
            venue_info = {
                "id": v.id,
                "name": v.name,
                "city": v.city,
                "address": v.address,
                "area": v.area,
            }
    # 参展展商数（优先参展关系表，无关系时回落已占用展位；用于列表/详情的"X 家展商"）
    if exhibitor_count is None:
        exhibitor_count = _exhibitor_count_map(db, [exh.id]).get(exh.id, 0)

    return {
        "id": exh.id,
        "title": exh.title,
        "name": exh.title,  # frontend alias for title
        "title_en": exh.title_en,
        "description": exh.description,
        "description_en": exh.description_en,
        "cover_image": exh.cover_image,
        "cover_url": exh.cover_image,  # frontend alias for cover_image
        "start_date": exh.start_date,
        "end_date": exh.end_date,
        "location": exh.location,
        "venue": exh.location,  # frontend alias for location
        "venue_info": venue_info,  # V3.1: 关联展馆信息(可选,含 id/name/city/address/area)
        "city": "",  # placeholder - backend does not separate city
        "address": exh.location,  # frontend field mapped to location
        "short_name": "",  # placeholder
        "total_booths": 0,  # placeholder
        "available_booths": 0,  # placeholder
        "visitor_count": exh.visitor_count or 0,
        "exhibitor_count": exhibitor_count,
        "status": exh.status,
        "organizer_id": exh.organizer_id,
        "organizer_name": exh.organizer_name,
        # V2.0
        "is_featured": exh.is_featured,
        "hot_score": exh.hot_score or 0,
        "created_at": exh.created_at.isoformat() if exh.created_at else None,
        "updated_at": exh.updated_at.isoformat() if exh.updated_at else None,
    }


def _paginated_response(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "list": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }


# ============================================================
# 端点
# ============================================================

@router.get("")
def get_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    timeline: Optional[str] = Query(
        default=None,
        description="时间线筛选: upcoming=即将举办 / ongoing=进行中 / ended=已结束（按日期推导）",
    ),
    search: Optional[str] = Query(default=None),
    organizer_id: Optional[int] = Query(default=None, description="按主办方过滤（前端 getMyExhibitions 一直传该参数，此前被忽略导致分页总数失真）"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """获取展会列表（分页 + 筛选 + 搜索）

    公开可见口径：status 不在 ('draft','cancelled') 里。
    - 未显式传 status：管理员（role == 'admin'）看全部；游客/普通用户排除 draft/cancelled。
    - 显式传 status：按传入值过滤，行为不变（管理员与普通用户一致）。
    """
    q = db.query(Exhibition)

    if status:
        # 显式筛选：原样过滤（管理员要查 draft 就传 status=draft）
        q = q.filter(Exhibition.status == status)
    elif not (current_user and current_user.role == "admin"):
        # 默认（游客/普通用户）：草稿与已取消不对外，与 public_stats 同口径
        q = q.filter(Exhibition.status.notin_(HIDDEN_EXHIBITION_STATUS))

    if organizer_id:
        q = q.filter(Exhibition.organizer_id == organizer_id)

    # 时间线筛选：库内日期为 ISO 字符串，同格式下字典序即时间序
    # （历史脏数据如 '0123-…' 会被自然归入"已结束"）
    if timeline in ("upcoming", "ongoing", "ended"):
        now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if timeline == "upcoming":
            q = q.filter(Exhibition.start_date >= now_iso)
        elif timeline == "ongoing":
            q = q.filter(Exhibition.start_date <= now_iso, Exhibition.end_date >= now_iso)
        else:
            q = q.filter(Exhibition.end_date < now_iso)

    if search:
        q = q.filter(
            or_(
                Exhibition.title.ilike(f"%{search}%"),
                Exhibition.description.ilike(f"%{search}%"),
                Exhibition.location.ilike(f"%{search}%"),
            )
        )

    total = q.count()
    if timeline == "upcoming":
        q = q.order_by(Exhibition.start_date.asc())   # 最近要开的排最前
    elif timeline == "ended":
        q = q.order_by(Exhibition.end_date.desc())    # 最近结束的排最前
    else:
        q = q.order_by(Exhibition.created_at.desc())
    exhibitions = q.offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # 展商数批量算（关系表优先 + booths 回落），固定 2 条查询
    count_map = _exhibitor_count_map(db, [e.id for e in exhibitions])

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_exhibition_to_dict(e, db, count_map.get(e.id, 0)) for e in exhibitions],
            total, page, page_size,
        ),
    }


# ============================================================
# V2.0: 首页精选 & 热门
# ============================================================

@router.get("/featured")
def get_featured(
    limit: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """首页精选展会（重磅来袭）

    优先返回 is_featured=True 的展会，按 hot_score 降序。
    不足 limit 条时用最新发布的展会补齐。
    """
    featured = db.query(Exhibition).filter(
        Exhibition.is_featured == True,
        Exhibition.status.in_(["published", "ongoing"]),
    ).order_by(Exhibition.hot_score.desc()).limit(limit).all()

    # 精选不够，用最新发布补齐
    if len(featured) < limit:
        exclude_ids = [e.id for e in featured]
        extra = db.query(Exhibition).filter(
            Exhibition.status.in_(["published", "ongoing"]),
            ~Exhibition.id.in_(exclude_ids) if exclude_ids else True,
        ).order_by(Exhibition.created_at.desc()).limit(limit - len(featured)).all()
        featured.extend(extra)

    count_map = _exhibitor_count_map(db, [e.id for e in featured])
    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": [_exhibition_to_dict(e, db, count_map.get(e.id, 0)) for e in featured],
    }


@router.get("/hot")
def get_hot(
    limit: int = Query(default=10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """热门展会 Top N（按 hot_score 降序）"""
    hot = db.query(Exhibition).filter(
        Exhibition.status.in_(["published", "ongoing"]),
    ).order_by(Exhibition.hot_score.desc()).limit(limit).all()

    count_map = _exhibitor_count_map(db, [e.id for e in hot])
    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": [_exhibition_to_dict(e, db, count_map.get(e.id, 0)) for e in hot],
    }


@router.get("/upcoming")
def get_upcoming(
    # 首页「重磅发布」一次取满 100 条，由前端切片「查看更多」，故上限放到 100
    limit: int = Query(default=6, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """即将开幕的展会（开始日期在未来的已发布展会，按开始时间升序）

    修复：此前实现未过滤日期，已结束的展会也会排在前面
    （首页"重磅来袭/即将开幕"展示位会被历史展会占据）。
    """
    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    upcoming = db.query(Exhibition).filter(
        Exhibition.status == "published",
        Exhibition.start_date >= now_iso,
    ).order_by(Exhibition.start_date.asc()).limit(limit).all()

    count_map = _exhibitor_count_map(db, [e.id for e in upcoming])
    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": [_exhibition_to_dict(e, db, count_map.get(e.id, 0)) for e in upcoming],
    }


@router.get("/registrations")
def get_registrations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """展会报名概览（仅平台管理员）

    2026-10-19：主办方角色取消后，此端点返回平台全部展会。
    """
    if current_user.role != "admin":
        raise Forbidden(message="仅平台管理员可查看")
    q = db.query(Exhibition)
    total = q.count()
    exhibitions = q.order_by(Exhibition.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    count_map = _exhibitor_count_map(db, [e.id for e in exhibitions])
    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(
            [_exhibition_to_dict(e, db, count_map.get(e.id, 0)) for e in exhibitions],
            total, page, page_size,
        ),
    }


# ============================================================
# 参展关系口径：展会详情页的「展商 / 展品 / 统计」
# ============================================================
#
# 数据模型（2026-10-19 重构为干净的多对多）：
#
#   exhibitions 1 ──< exhibition_exhibitors >── 1 catalog_exhibitors ──< catalog_products
#
# - **参展关系唯一来源是 `exhibition_exhibitors`**：一间展商参加多场 / 多届展会就有
#   多条关系，每场一条（`expo_label` 存名录原文展会名、`booth_no` 存该届展位号），
#   不再把同一展商压成一条、只能挂一个展会；
# - 展商 = `exhibition_exhibitors` JOIN `catalog_exhibitors`；
# - 展品 = 上述展商 JOIN `catalog_products`（按 `catalog_products.exhibitor_id`）；
# - `catalog_exhibitors.exhibition_id` / `expo_name` 降级为**导入期遗留列**，
#   接口层不再读取（遗留列原样保留，不删数据）；
# - 名录对某展会完全没有关系时，仍回落到原逻辑（booths / products 表），
#   供平台自建展会使用，响应字段与分页参数保持不变。
#
# 改造前的「弱三层 + 字符串别名补齐」实现（`_catalog_expo_aliases` /
# `_catalog_scope`，按 `expo_name` 与 `exhibitions.title` 硬凑）已删除：
# 那套逻辑在 `catalog_exhibitors.exhibition_id` 只有 48.8% 有值时把未对齐行补进来，
# 与关系表并存会**双算**，且无法表达"同一展商参加多届"。
# 关系表回填见 `scripts/backfill_exhibition_exhibitors.py`。


def _relation_exhibitor_total(db: Session, exhibition_id: int) -> int:
    """该展会的参展展商数（只查关系表，一条 COUNT）。

    唯一约束 `(exhibition_id, catalog_exhibitor_id)` 保证同一展商在同一展会
    只有一条关系，所以 COUNT 天然去重，不需要 DISTINCT。
    """
    return int(
        db.query(func.count(ExhibitionExhibitor.id))
        .filter(ExhibitionExhibitor.exhibition_id == exhibition_id)
        .scalar()
        or 0
    )


def _relation_product_total(db: Session, exhibition_id: int) -> int:
    """该展会名录展品数：关系表 → 展商 → `catalog_products.exhibitor_id`。

    每条关系对应该展商全部展品；关系在本展会内唯一，所以不会重复计数。
    """
    return int(
        db.query(func.count(CatalogProduct.id))
        .select_from(ExhibitionExhibitor)
        .join(
            CatalogProduct,
            CatalogProduct.exhibitor_id == ExhibitionExhibitor.catalog_exhibitor_id,
        )
        .filter(ExhibitionExhibitor.exhibition_id == exhibition_id)
        .scalar()
        or 0
    )


def _relation_stats(db: Session, exhibition_id: int) -> dict:
    """按关系表算真实聚合：展商 / 展品 / 城市 / 行业。

    - 展商数：关系表命中行数（一条 COUNT）；
    - 展品数：关系表 → 展商 → 展品计数（一条 COUNT）；
    - 城市 / 行业：distinct，且空串与 NULL 都不计入（来源数据里大量为空）。
    """
    base = (
        db.query(CatalogExhibitor)
        .select_from(ExhibitionExhibitor)
        .join(
            CatalogExhibitor,
            CatalogExhibitor.id == ExhibitionExhibitor.catalog_exhibitor_id,
        )
        .filter(ExhibitionExhibitor.exhibition_id == exhibition_id)
    )

    def _distinct(column) -> int:
        return int(
            base.with_entities(
                func.count(func.distinct(func.nullif(func.trim(column), "")))
            ).scalar()
            or 0
        )

    return {
        "exhibitors": _relation_exhibitor_total(db, exhibition_id),
        "products": _relation_product_total(db, exhibition_id),
        "cities": _distinct(CatalogExhibitor.city),
        "industries": _distinct(CatalogExhibitor.industry),
    }


def _product_first_image(images) -> str:
    """products.images 是 JSON 数组字符串；取第一张图，解析失败就把原串当地址。"""
    if not images:
        return ""
    if isinstance(images, list):
        parsed = images
    else:
        try:
            parsed = json.loads(str(images))
        except (TypeError, ValueError):
            return str(images).strip()
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, str) and item.strip():
                return item.strip()
        return ""
    return str(images).strip() if isinstance(images, str) else ""


@router.get("/{exhibition_id}/stats")
def get_exhibition_stats(
    exhibition_id: int,
    db: Session = Depends(get_db),
):
    """展会真实聚合：{exhibitors, products, cities, industries}

    供详情页顶部统计条「展商 N · 展品 M · 覆盖城市 K · 行业 J」使用。
    数字全部来自**参展关系表** join 名录快照的真实计数，不做任何放大/估算，
    也不再读取 `catalog_exhibitors.exhibition_id` / `expo_name`。
    """
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _relation_stats(db, exhibition_id),
    }


@router.get("/{exhibition_id}/products")
def get_exhibition_products(
    exhibition_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """展会名录展品（详情页「展品」区块，分页）

    口径：`exhibition_exhibitors` → `catalog_products.exhibitor_id`（与 /stats 同源）。
    该展会没有任何参展关系 / 名录展品时，回落到 products 表按 exhibition_id 的旧口径。
    """
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    total = _relation_product_total(db, exhibition_id)
    start = (page - 1) * page_size

    if total:
        rows = (
            db.query(
                CatalogProduct.id,
                CatalogProduct.name,
                CatalogProduct.category,
                CatalogProduct.image,
                CatalogProduct.exhibitor_name,
            )
            .select_from(ExhibitionExhibitor)
            .join(
                CatalogProduct,
                CatalogProduct.exhibitor_id
                == ExhibitionExhibitor.catalog_exhibitor_id,
            )
            .filter(ExhibitionExhibitor.exhibition_id == exhibition_id)
            .order_by(CatalogProduct.id.asc())
            .offset(start)
            .limit(page_size)
            .all()
        )
        items = [
            {
                "id": r.id,
                "name": r.name,
                "category": r.category or "",
                "image": r.image or "",
                "exhibitor_name": r.exhibitor_name or "",
                "source": "catalog",
            }
            for r in rows
        ]
    else:
        # ---- 回落：平台自建 products 表（无名录数据的展会）----
        q = db.query(Product).filter(Product.exhibition_id == exhibition_id)
        total = int(q.count() or 0)
        rows = q.order_by(Product.id.asc()).offset(start).limit(page_size).all()
        items = [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category or "",
                "image": _product_first_image(p.images),
                "exhibitor_name": p.exhibitor_name or "",
                "source": "products",
            }
            for p in rows
        ]

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(items, total, page, page_size),
    }


@router.get("/{exhibition_id}/exhibitors")
def get_exhibition_exhibitors(
    exhibition_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """展会参展展商名录（供详情页「参展展商」区块，分页 + total）

    取数优先级：
    1. **参展关系表** `exhibition_exhibitors` JOIN `catalog_exhibitors`（真实公开
       名录；一间展商参展多届会有多条关系，本接口只取本展会那条）—— 字段
       name/industry/city/product_count，按展品数降序（与 /catalog/exhibitors 同序）；
    2. 关系表里没有该展会的展商时回落到原逻辑（booths 已占用展位 → 平台展商账号），
       字段保持 company/booth_number/industry_domain/region/products_count 不变
       （老调用方与 tests/test_exhibitions_timeline_exhibitors.py 依赖该形状）。
    """
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    total = _relation_exhibitor_total(db, exhibition_id)
    start = (page - 1) * page_size

    if total:
        rows = (
            db.query(
                CatalogExhibitor.id,
                CatalogExhibitor.name,
                CatalogExhibitor.industry,
                CatalogExhibitor.city,
                CatalogExhibitor.product_count,
            )
            .select_from(ExhibitionExhibitor)
            .join(
                CatalogExhibitor,
                CatalogExhibitor.id == ExhibitionExhibitor.catalog_exhibitor_id,
            )
            .filter(ExhibitionExhibitor.exhibition_id == exhibition_id)
            .order_by(CatalogExhibitor.product_count.desc(), CatalogExhibitor.id.asc())
            .offset(start)
            .limit(page_size)
            .all()
        )
        items = [
            {
                "exhibitor_id": r.id,
                "name": r.name,
                "industry": r.industry or "",
                "city": r.city or "",
                "product_count": int(r.product_count or 0),
                "source": "catalog",
            }
            for r in rows
        ]
        return {
            "success": True,
            "code": "OK",
            "message": "获取成功",
            "data": _paginated_response(items, total, page, page_size),
        }

    # ---- 回落：原 booths 口径（同一展商多个展位只列一次，保留展位号最小者）----
    booths = db.query(Booth).filter(
        Booth.exhibition_id == exhibition_id,
        Booth.exhibitor_id.isnot(None),
    ).order_by(Booth.booth_number.asc()).all()

    seen, unique = set(), []
    for b in booths:
        if b.exhibitor_id in seen:
            continue
        seen.add(b.exhibitor_id)
        unique.append(b)

    total = len(unique)
    page_rows = unique[start:start + page_size]

    ids = [b.exhibitor_id for b in page_rows]
    users = {}
    mbs = {}
    product_counts = {}
    if ids:
        users = {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()}
        mbs = {m.exhibitor_id: m for m in db.query(MicroBooth).filter(MicroBooth.exhibitor_id.in_(ids)).all()}
        product_counts = dict(
            db.query(Product.exhibitor_id, func.count(Product.id))
            .filter(Product.exhibitor_id.in_(ids))
            .group_by(Product.exhibitor_id)
            .all()
        )

    items = []
    for b in page_rows:
        u = users.get(b.exhibitor_id)
        mb = mbs.get(b.exhibitor_id)
        items.append({
            "exhibitor_id": b.exhibitor_id,
            "username": u.username if u else None,
            "company": (u.company if u and u.company else None)
                       or (b.company_name or b.exhibitor_name)
                       or (u.username if u else ""),
            "booth_number": b.booth_number,
            "booth_size": b.size,
            "location_area": b.location_area,
            "industry_domain": (u.industry_domain if u else None) or (mb.industry_domain if mb else None),
            "region": u.region if u else None,
            "membership_tier": mb.membership_tier if mb else None,
            "products_count": product_counts.get(b.exhibitor_id, 0),
            "source": "booth",
        })

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _paginated_response(items, total, page, page_size),
    }


@router.get("/{exhibition_id}")
def get_by_id(
    exhibition_id: int,
    db: Session = Depends(get_db),
):
    """获取展会详情"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _exhibition_to_dict(exh, db),
    }


@router.post("")
def create(
    data: ExhibitionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """创建展会（平台自营：仅平台管理员可创建）"""
    if current_user.role != "admin":
        raise Forbidden(message="仅平台管理员可创建展会（主办方角色已于 2026-10-19 取消）")

    # 日期校验：格式 / 年份区间 / 先后顺序（不合法抛 400）
    _validate_exhibition_dates(data.start_date, data.end_date)

    # V3.1: 校验关联展馆存在
    venue_id = data.venue_id
    if venue_id is not None:
        venue = db.query(Venue).filter(Venue.id == venue_id).first()
        if not venue:
            raise NotFound(message="展馆不存在")

    exh = Exhibition(
        title=data.title,
        description=data.description,
        cover_image=data.cover_image,
        start_date=data.start_date,
        end_date=data.end_date,
        location=data.location,
        venue_id=venue_id,
        status=data.status or "draft",
        organizer_id=current_user.id,
        organizer_name=PLATFORM_OPERATOR_NAME,
    )
    db.add(exh)
    db.commit()
    db.refresh(exh)

    return {
        "success": True,
        "code": "OK",
        "message": "展会创建成功",
        "data": _exhibition_to_dict(exh, db),
    }


@router.put("/{exhibition_id}")
def update(
    exhibition_id: int,
    data: ExhibitionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """更新展会信息"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    # 权限检查：平台管理员可编辑全部展会（平台自营）
    if current_user.role != "admin":
        raise Forbidden(message="无权编辑此展会")

    updates = data.model_dump(exclude_unset=True)
    # 日期校验：只校验本次提交的字段；未提交的一侧用库内旧值参与先后比较
    if "start_date" in updates or "end_date" in updates:
        _validate_exhibition_dates(
            updates.get("start_date"),
            updates.get("end_date"),
            existing_start=exh.start_date,
            existing_end=exh.end_date,
        )
    # V3.2: venue_id 变更时校验展馆存在
    if "venue_id" in updates and updates["venue_id"] is not None:
        venue = db.query(Venue).filter(Venue.id == updates["venue_id"]).first()
        if not venue:
            raise NotFound(message="展馆不存在")
    for field, value in updates.items():
        if hasattr(exh, field):
            setattr(exh, field, value)

    db.commit()
    db.refresh(exh)

    return {
        "success": True,
        "code": "OK",
        "message": "展会更新成功",
        "data": _exhibition_to_dict(exh, db),
    }


@router.delete("/{exhibition_id}")
def delete(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """删除展会"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    if current_user.role != "admin":
        raise Forbidden(message="无权删除此展会")

    # 2026-10-19 修复：展会下挂 6 张子表（booths/products/registrations/reviews/appointments/procurements），
    # 直接 DELETE 会撞外键 500。这里按"展位/报名/评价/预约 随展删除；
    # 展商展品与采购需求只解绑不删除（属于展商/采购商资产）；有已支付订单则拒绝删除"。
    from app.models.booth import Booth
    from app.models.registration import Registration
    from app.models.review import Review
    from app.models.appointment import Appointment
    from app.models.procurement import Procurement
    from app.models.product import Product
    from app.modules.ticketing.models import TicketType, TicketingOrder

    paid = db.query(TicketingOrder).filter(
        TicketingOrder.exhibition_id == exhibition_id,
        TicketingOrder.status == "paid",
    ).count()
    if paid:
        raise BadRequest(message=f"该展会已有 {paid} 笔已支付订单，不能删除（先处理退款与订单归档）")

    db.query(TicketingOrder).filter(TicketingOrder.exhibition_id == exhibition_id).delete(synchronize_session=False)
    db.query(TicketType).filter(TicketType.exhibition_id == exhibition_id).delete(synchronize_session=False)
    db.query(Review).filter(Review.exhibition_id == exhibition_id).delete(synchronize_session=False)
    db.query(Appointment).filter(Appointment.exhibition_id == exhibition_id).delete(synchronize_session=False)
    db.query(Registration).filter(Registration.exhibition_id == exhibition_id).delete(synchronize_session=False)
    # 展品解绑（含归属已删展位的展品），不删展商资产
    db.query(Product).filter(Product.exhibition_id == exhibition_id).update(
        {Product.exhibition_id: None, Product.booth_id: None}, synchronize_session=False)
    db.query(Procurement).filter(Procurement.exhibition_id == exhibition_id).update(
        {Procurement.exhibition_id: None}, synchronize_session=False)
    db.query(Booth).filter(Booth.exhibition_id == exhibition_id).delete(synchronize_session=False)

    db.delete(exh)
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "展会已删除（展位/报名/评价/预约一并清理，展商展品与采购需求已解绑保留）",
        "data": None,
    }


@router.post("/{exhibition_id}/register")
def register(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """报名参加展会（展商报名）"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    if exh.status not in ("published", "ongoing"):
        raise BadRequest(message="展会未开放报名")

    # 简化：将用户设为展会的关注者
    # 实际项目中应通过中间表记录报名关系
    return {
        "success": True,
        "code": "OK",
        "message": "报名成功",
        "data": {
            "exhibition_id": exh.id,
            "user_id": current_user.id,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.delete("/{exhibition_id}/register")
def unregister(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """取消展会报名"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    return {
        "success": True,
        "code": "OK",
        "message": "已取消报名",
        "data": None,
    }


@router.post("/{exhibition_id}/approve")
def approve(
    exhibition_id: int,
    data: ExhibitionApproveRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """审批展会（仅平台管理员）"""
    if current_user.role != "admin":
        raise Forbidden(message="无权审批展会")

    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    if data.approved:
        exh.status = "published"
    else:
        exh.status = "draft"

    db.commit()
    db.refresh(exh)

    return {
        "success": True,
        "code": "OK",
        "message": "审批完成" if data.approved else "已驳回",
        "data": _exhibition_to_dict(exh, db),
    }

@router.post("/{exhibition_id}/publish")
def publish(
    exhibition_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """发布展会（设置状态为 published）"""
    exh = db.query(Exhibition).filter(Exhibition.id == exhibition_id).first()
    if not exh:
        raise NotFound(message="展会不存在")

    # 权限：仅平台管理员可发布（平台自营展会）
    if current_user.role != "admin":
        raise Forbidden(message="无权发布此展会")

    exh.status = "published"
    db.commit()
    db.refresh(exh)

    return {
        "success": True,
        "code": "OK",
        "message": "展会发布成功",
        "data": _exhibition_to_dict(exh, db),
    }



# ============================================================
# AI 语义搜索
# ============================================================

def _product_to_dict(p) -> dict:
    return {
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'category': p.category,
        'price': p.price,
        'unit': p.unit,
        'images': p.images,
        'stock': p.stock,
        'status': p.status,
        'booth_id': p.booth_id,
        'exhibition_id': p.exhibition_id,
        'exhibitor_id': p.exhibitor_id,
        'exhibitor_name': p.exhibitor_name,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


def _booth_to_dict(b) -> dict:
    return {
        'id': b.id,
        'exhibition_id': b.exhibition_id,
        'booth_number': b.booth_number,
        'exhibitor_id': b.exhibitor_id,
        'exhibitor_name': b.exhibitor_name,
        'company_name': b.company_name,
        'size': b.size,
        'location_area': b.location_area,
        'price': b.price,
        'status': b.status,
        'description': b.description,
        'created_at': b.created_at.isoformat() if b.created_at else None,
    }


@router.get('/search/smart')
def smart_search(q: str = Query(...), db: Session = Depends(get_db)):
    # Search exhibitions, products, booths by keyword
    # Return combined results ranked by relevance
    results = {'exhibitions': [], 'products': [], 'booths': []}
    like = f'%{q}%'
    from app.models.exhibition import Exhibition
    from app.models.product import Product
    from app.models.booth import Booth

    results['exhibitions'] = []
    matched = db.query(Exhibition).filter(
        Exhibition.title.ilike(like)).limit(5).all()
    matched_count_map = _exhibitor_count_map(db, [e.id for e in matched])
    results['exhibitions'] = [
        _exhibition_to_dict(e, db, matched_count_map.get(e.id, 0)) for e in matched
    ]

    results['products'] = [_product_to_dict(p) for p in db.query(Product).filter(
        Product.name.ilike(like)).limit(5).all()]

    results['booths'] = [_booth_to_dict(b) for b in db.query(Booth).filter(
        Booth.booth_number.ilike(like)).limit(5).all()]

    total = len(results['exhibitions']) + len(results['products']) + len(results['booths'])
    return {'success': True, 'code': 'OK', 'data': results, 'total': total}

