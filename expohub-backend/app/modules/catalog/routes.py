"""
展商名录 / 展品库只读路由（Catalog）

数据是**第三方公开名录导入的快照**（约 3.1 万展商 / 7 万展品），不是平台账号，
因此本模块只有读接口，全部公开（不需要登录）：

- GET /api/catalog/exhibitors          展商列表（搜索 + 行业/城市/展会筛选 + facets）
- GET /api/catalog/exhibitors/{id}     展商详情（含名录展品 Top 12）
- GET /api/catalog/products            展品列表（搜索 + 类目/展会筛选 + facets）
- GET /api/catalog/products/{id}       展品详情（含归属展商摘要，可空）
- GET /api/catalog/stats               目录维度统计（distinct 计数）

所属展会口径（2026-10-19 起）：展商的 `exhibition_id` / `exhibition_ids` 一律来自
参展关系表 `exhibition_exhibitors`（一个展商可参加多场，多对多），
`?exhibition_id=` 筛选也走关系表；遗留列 `catalog_exhibitors.exhibition_id`
（31,938 行里只有 16,353 行有值、且一展商只能挂一场）不再被接口读取。

性能口径（3 万 + 7 万行）：
1. 列表只查"需要返回的列"，**不取** description / main_business / detail_html
   这类大字段（用"单独列查询"而不是 load_only，SQL 里根本不出现在 SELECT 中）；
2. facets 固定 2-3 条 GROUP BY（每个维度一条），绝不按记录逐条查；
3. 详情页关联数据各 1 条批量查询，没有循环查库（无 N+1）；
4. 列表排序 `product_count DESC, id ASC` / `id DESC` 都能命中已有索引。

统一响应格式沿用项目既有口径（参考 app/modules/expo/exhibitions.py）：
    {"success": True, "code": "OK", "message": "获取成功", "data": {...}}
404 走 app.core.exceptions.NotFound，由全局处理器输出
    {"success": False, "code": "NOT_FOUND", "message": "...", "detail": {...}}
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFound
from app.models.base import get_db
from app.models.catalog import CatalogExhibitor, CatalogProduct
from app.models.exhibition_exhibitor import ExhibitionExhibitor

router = APIRouter(prefix="/catalog", tags=["展商名录"])

# ---- 常量 ----
FACET_LIMIT = 20            # facets 每个维度取前 20
DETAIL_PRODUCT_LIMIT = 12   # 展商详情里最多带 12 条展品
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# ============================================================
# 通用小工具
# ============================================================

def _ok(data: Any) -> dict:
    """统一成功响应（与 exhibitions.py / public_stats.py 保持一致）"""
    return {"success": True, "code": "OK", "message": "获取成功", "data": data}


def _clean(value: Optional[str]) -> Optional[str]:
    """查询参数归一化：None 或空串/纯空白 → None（不参与筛选）。

    前端经常把没填的筛选条件以 `industry=` 形式发上来，这里统一当"不筛选"，
    避免 `= ''` 把整页结果筛空。
    """
    if value is None:
        return None
    text = value.strip()
    return text or None


def _page_args(
    page: Optional[int], page_size: Optional[int]
) -> Tuple[int, int]:
    """分页参数归一化：缺失给默认值，越界就夹紧（不抛 422）。

    - page 缺失/非正数 → 1
    - page_size 缺失 → 20；上限 100（超过的按 100 处理）
    """
    try:
        page_no = int(page) if page is not None else 1
    except (TypeError, ValueError):
        page_no = 1
    try:
        size = int(page_size) if page_size is not None else DEFAULT_PAGE_SIZE
    except (TypeError, ValueError):
        size = DEFAULT_PAGE_SIZE
    if page_no < 1:
        page_no = 1
    if size < 1:
        size = DEFAULT_PAGE_SIZE
    if size > MAX_PAGE_SIZE:
        size = MAX_PAGE_SIZE
    return page_no, size


def _like(keyword: str) -> str:
    """构造 ilike 模式串（与项目其它模块一致，不做 % / _ 转义）"""
    return f"%{keyword}%"


def _positive_int(value: Optional[str]) -> Optional[int]:
    """可选 id 类查询参数归一化：空串 / 非数字 / <= 0 → None（不筛选）。

    与 `_page_args` 同款宽松口径：公开只读接口不因为前端传了空筛选条件
    （`?exhibition_id=`）就返回 422，宁可当"没填"。
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = int(text)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _facet_counts(
    db: Session,
    column,
    model,
    conditions: Sequence,
) -> List[Dict[str, Any]]:
    """对"当前筛选后的结果集"按某一列做一次 GROUP BY，取 top 20。

    一条 SQL 出一整个维度：
        SELECT industry, count(*) FROM catalog_exhibitors
        WHERE <当前筛选条件> AND industry IS NOT NULL AND industry != ''
        GROUP BY industry ORDER BY count(*) DESC, industry ASC LIMIT 20

    Args:
        db: 会话
        column: 需要聚合的列（industry / city / expo_name / category）
        model: 对应模型（CatalogExhibitor / CatalogProduct）
        conditions: 当前生效的筛选条件（与列表查询同源，保证口径一致）

    Returns:
        [{"value": <列值>, "count": <条数>}, ...]；空值（NULL / ''）不计入
    """
    rows = (
        db.query(column, func.count().label("cnt"))
        .select_from(model)
        .filter(*conditions)
        .filter(column.isnot(None), column != "")
        .group_by(column)
        # 主序按条数倒序；同数时按值升序，保证分页/多次请求结果稳定
        .order_by(func.count().desc(), column.asc())
        .limit(FACET_LIMIT)
        .all()
    )
    return [{"value": value, "count": count} for value, count in rows]


# ============================================================
# 展商列表 / 详情
# ============================================================

def _exhibitor_conditions(
    search: Optional[str],
    industry: Optional[str],
    city: Optional[str],
    expo: Optional[str],
    exhibition_id: Optional[int] = None,
) -> List:
    """展商列表筛选条件（列表、总数、facets 三处共用同一份条件）

    `exhibition_id` 按**参展关系表** `exhibition_exhibitors` 筛（不是遗留列
    `catalog_exhibitors.exhibition_id`）：一个展商参加多届展会时有多条关系，
    这里用 IN (子查询) 命中任一场即可，且与展会详情页 / 首页计数同口径。
    """
    conditions: List = []
    if search:
        pattern = _like(search)
        conditions.append(
            or_(
                CatalogExhibitor.name.ilike(pattern),
                CatalogExhibitor.name_en.ilike(pattern),
                CatalogExhibitor.main_business.ilike(pattern),
            )
        )
    if industry:
        conditions.append(CatalogExhibitor.industry == industry)
    if city:
        conditions.append(CatalogExhibitor.city == city)
    if expo:
        conditions.append(CatalogExhibitor.expo_name == expo)
    if exhibition_id is not None:
        conditions.append(
            CatalogExhibitor.id.in_(
                select(ExhibitionExhibitor.catalog_exhibitor_id).where(
                    ExhibitionExhibitor.exhibition_id == exhibition_id
                )
            )
        )
    return conditions


def _exhibition_ids_by_exhibitor(
    db: Session, exhibitor_ids: Sequence[int]
) -> Dict[int, List[int]]:
    """批量取「展商 → 所属展会 id 列表」（来自参展关系表，一条 SQL，无 N+1）。

    为什么不是 `catalog_exhibitors.exhibition_id`：那是导入期遗留列（31,938 行里
    只有 16,353 行有值），且一个展商只能挂一场，与关系表的真实参赛历史不一致。

    Args:
        db: 会话
        exhibitor_ids: 本页展商 id

    Returns:
        {exhibitor_id: [exhibition_id, ...]}，每个列表按 exhibition_id 升序；
        没有关系的展商不出现在返回值里（调用方按"无展会"处理）
    """
    ids = [int(i) for i in exhibitor_ids if i is not None]
    if not ids:
        return {}
    rows = (
        db.query(
            ExhibitionExhibitor.catalog_exhibitor_id,
            ExhibitionExhibitor.exhibition_id,
        )
        .filter(ExhibitionExhibitor.catalog_exhibitor_id.in_(ids))
        .order_by(
            ExhibitionExhibitor.catalog_exhibitor_id.asc(),
            ExhibitionExhibitor.exhibition_id.asc(),
        )
        .all()
    )
    mapping: Dict[int, List[int]] = {}
    for catalog_exhibitor_id, exhibition_id in rows:
        if catalog_exhibitor_id is None or exhibition_id is None:
            continue
        mapping.setdefault(int(catalog_exhibitor_id), []).append(int(exhibition_id))
    return mapping


# 展商列表要返回的列（显式列查询：description / main_business 不进 SELECT）
# 注意：不含 `catalog_exhibitors.exhibition_id`（遗留弱关联列）——所属展会改为
# 从参展关系表 `exhibition_exhibitors` 批量取，见 `_exhibition_ids_by_exhibitor`。
_EXHIBITOR_LIST_COLUMNS = (
    CatalogExhibitor.id,
    CatalogExhibitor.name,
    CatalogExhibitor.name_en,
    CatalogExhibitor.expo_name,
    CatalogExhibitor.industry,
    CatalogExhibitor.city,
    CatalogExhibitor.country,
    CatalogExhibitor.booth_no,
    CatalogExhibitor.product_count,
    CatalogExhibitor.website,
)


def _exhibitor_row_to_dict(
    row, exhibition_ids: Optional[Sequence[int]] = None
) -> Dict[str, Any]:
    """把列表查询的 Row 转成接口字段（保持契约里的字段顺序）

    所属展会字段口径（2026-10-19 起）：
    - `exhibition_ids`: 该展商在参展关系表里的全部展会 id（升序，可能为空列表）；
    - `exhibition_id`: 兼容旧前端的单个字段，取 `exhibition_ids[0]`（无关系时 None）。
      注意它**不再**来自遗留列 `catalog_exhibitors.exhibition_id`。
    """
    ids = list(exhibition_ids or [])
    return {
        "id": row.id,
        "name": row.name,
        "name_en": row.name_en,
        "expo_name": row.expo_name,
        "exhibition_id": ids[0] if ids else None,
        "exhibition_ids": ids,
        "industry": row.industry,
        "city": row.city,
        "country": row.country,
        "booth_no": row.booth_no,
        "product_count": row.product_count or 0,
        "website": row.website,
    }


@router.get("/exhibitors")
def list_exhibitors(
    search: Optional[str] = Query(default=None, description="模糊匹配展商名/英文名/主营业务"),
    industry: Optional[str] = Query(default=None, description="行业（精确匹配）"),
    city: Optional[str] = Query(default=None, description="城市（精确匹配）"),
    expo: Optional[str] = Query(default=None, description="展会名称（精确匹配）"),
    exhibition_id: Optional[str] = Query(
        default=None,
        description="展会 id（按参展关系表筛选；空/非法值视为不筛选，与展会详情页计数同口径）",
    ),
    page: Optional[int] = Query(default=None, description="页码，默认 1"),
    page_size: Optional[int] = Query(
        default=None, description=f"每页条数，默认 {DEFAULT_PAGE_SIZE}，上限 {MAX_PAGE_SIZE}"
    ),
    db: Session = Depends(get_db),
):
    """展商列表（公开）

    排序：`product_count DESC, id ASC`（展品多的靠前，同数按 id 稳定排序）。

    facets 口径：对**当前筛选后的结果集**（search + industry + city + expo +
    exhibition_id 全部生效）再做 GROUP BY，因此选完"城市=上海"后 cities 分面会只剩上海一项。

    所属展会口径：`exhibition_ids` / `exhibition_id` 来自参展关系表
    `exhibition_exhibitors`（不再读遗留列 `catalog_exhibitors.exhibition_id`）。
    """
    search = _clean(search)
    industry = _clean(industry)
    city = _clean(city)
    expo = _clean(expo)
    exhibition_id_value = _positive_int(exhibition_id)
    page_no, size = _page_args(page, page_size)

    conditions = _exhibitor_conditions(
        search, industry, city, expo, exhibition_id_value
    )

    # 1) 总数（走索引 / 覆盖索引，不物化实体）
    total = (
        db.query(func.count(CatalogExhibitor.id))
        .select_from(CatalogExhibitor)
        .filter(*conditions)
        .scalar()
        or 0
    )

    # 2) facets：3 条 GROUP BY（行业 / 城市 / 展会）
    facets = {
        "industries": _facet_counts(db, CatalogExhibitor.industry, CatalogExhibitor, conditions),
        "cities": _facet_counts(db, CatalogExhibitor.city, CatalogExhibitor, conditions),
        "expos": _facet_counts(db, CatalogExhibitor.expo_name, CatalogExhibitor, conditions),
    }

    # 3) 当页数据（只取返回需要的列，避免把大字段带走）
    rows = (
        db.query(*_EXHIBITOR_LIST_COLUMNS)
        .filter(*conditions)
        .order_by(CatalogExhibitor.product_count.desc(), CatalogExhibitor.id.asc())
        .offset((page_no - 1) * size)
        .limit(size)
        .all()
    )

    # 4) 所属展会：一条批量查询（关系表），无 N+1
    exhibition_map = _exhibition_ids_by_exhibitor(db, [row.id for row in rows])

    return _ok({
        "list": [
            _exhibitor_row_to_dict(row, exhibition_map.get(row.id, [])) for row in rows
        ],
        "total": total,
        "page": page_no,
        "page_size": size,
        "facets": facets,
    })


@router.get("/exhibitors/{exhibitor_id}")
def get_exhibitor(exhibitor_id: int, db: Session = Depends(get_db)):
    """展商详情（公开）

    `data` = 列表字段 + company_type / scale / main_business / description / source
    + products（该展商在名录里的展品，按 id 升序，最多 12 条）。

    所属展会（`exhibition_ids` / `exhibition_id`）与列表同口径：来自参展关系表
    1 条查询，不再读遗留列 `catalog_exhibitors.exhibition_id`。
    """
    exhibitor = db.get(CatalogExhibitor, exhibitor_id)
    if exhibitor is None:
        raise NotFound(message="展商不存在", detail={"id": exhibitor_id})

    # 1 条查询取展品（只取 4 个字段，不含 detail_html），无 N+1
    product_rows = (
        db.query(
            CatalogProduct.id,
            CatalogProduct.name,
            CatalogProduct.category,
            CatalogProduct.image,
        )
        .filter(CatalogProduct.exhibitor_id == exhibitor_id)
        .order_by(CatalogProduct.id.asc())
        .limit(DETAIL_PRODUCT_LIMIT)
        .all()
    )

    # 1 条查询取所属展会（参展关系表，可能多条）
    exhibition_ids = _exhibition_ids_by_exhibitor(db, [exhibitor.id]).get(exhibitor.id, [])

    data = {
        "id": exhibitor.id,
        "name": exhibitor.name,
        "name_en": exhibitor.name_en,
        "expo_name": exhibitor.expo_name,
        "exhibition_id": exhibition_ids[0] if exhibition_ids else None,
        "exhibition_ids": exhibition_ids,
        "industry": exhibitor.industry,
        "city": exhibitor.city,
        "country": exhibitor.country,
        "booth_no": exhibitor.booth_no,
        "product_count": exhibitor.product_count or 0,
        "website": exhibitor.website,
        # ---- 详情额外字段 ----
        "company_type": exhibitor.company_type,
        "scale": exhibitor.scale,
        "main_business": exhibitor.main_business,
        "description": exhibitor.description,
        "source": exhibitor.source,
        "products": [
            {
                "id": row.id,
                "name": row.name,
                "category": row.category,
                "image": row.image,
            }
            for row in product_rows
        ],
    }
    return _ok(data)


# ============================================================
# 展品列表 / 详情
# ============================================================

def _product_conditions(
    search: Optional[str],
    category: Optional[str],
    expo: Optional[str],
) -> List:
    """展品列表筛选条件（列表、总数、facets 共用）"""
    conditions: List = []
    if search:
        pattern = _like(search)
        conditions.append(
            or_(
                CatalogProduct.name.ilike(pattern),
                CatalogProduct.category.ilike(pattern),
                CatalogProduct.application.ilike(pattern),
            )
        )
    if category:
        conditions.append(CatalogProduct.category == category)
    if expo:
        conditions.append(CatalogProduct.expo_name == expo)
    return conditions


# 展品列表要返回的列（detail_html 不进 SELECT）
_PRODUCT_LIST_COLUMNS = (
    CatalogProduct.id,
    CatalogProduct.name,
    CatalogProduct.category,
    CatalogProduct.application,
    CatalogProduct.price_spec,
    CatalogProduct.image,
    CatalogProduct.exhibitor_name,
    CatalogProduct.expo_name,
    CatalogProduct.exhibitor_id,
)


def _product_row_to_dict(row) -> Dict[str, Any]:
    """把列表查询的 Row 转成接口字段（保持契约里的字段顺序）"""
    return {
        "id": row.id,
        "name": row.name,
        "category": row.category,
        "application": row.application,
        "price_spec": row.price_spec,
        "image": row.image,
        "exhibitor_name": row.exhibitor_name,
        "expo_name": row.expo_name,
        "exhibitor_id": row.exhibitor_id,
    }


@router.get("/products")
def list_products(
    search: Optional[str] = Query(default=None, description="模糊匹配展品名/类目/应用领域"),
    category: Optional[str] = Query(default=None, description="类目（精确匹配）"),
    expo: Optional[str] = Query(default=None, description="展会名称（精确匹配）"),
    page: Optional[int] = Query(default=None, description="页码，默认 1"),
    page_size: Optional[int] = Query(
        default=None, description=f"每页条数，默认 {DEFAULT_PAGE_SIZE}，上限 {MAX_PAGE_SIZE}"
    ),
    db: Session = Depends(get_db),
):
    """展品列表（公开），排序 `id DESC`（最新导入的靠前）"""
    search = _clean(search)
    category = _clean(category)
    expo = _clean(expo)
    page_no, size = _page_args(page, page_size)

    conditions = _product_conditions(search, category, expo)

    total = (
        db.query(func.count(CatalogProduct.id))
        .select_from(CatalogProduct)
        .filter(*conditions)
        .scalar()
        or 0
    )

    # facets：2 条 GROUP BY（类目 / 展会）
    facets = {
        "categories": _facet_counts(db, CatalogProduct.category, CatalogProduct, conditions),
        "expos": _facet_counts(db, CatalogProduct.expo_name, CatalogProduct, conditions),
    }

    rows = (
        db.query(*_PRODUCT_LIST_COLUMNS)
        .filter(*conditions)
        .order_by(CatalogProduct.id.desc())
        .offset((page_no - 1) * size)
        .limit(size)
        .all()
    )

    return _ok({
        "list": [_product_row_to_dict(row) for row in rows],
        "total": total,
        "page": page_no,
        "page_size": size,
        "facets": facets,
    })


@router.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    """展品详情（公开）

    `data` = 列表字段 + detail_html / source + exhibitor（归属展商摘要，可空）。
    """
    product = db.get(CatalogProduct, product_id)
    if product is None:
        raise NotFound(message="展品不存在", detail={"id": product_id})

    # 展商摘要：1 条查询；exhibitor_id 为空或展商已不存在时返回 null
    exhibitor_info: Optional[Dict[str, Any]] = None
    if product.exhibitor_id is not None:
        exhibitor = db.get(CatalogExhibitor, product.exhibitor_id)
        if exhibitor is not None:
            exhibitor_info = {
                "id": exhibitor.id,
                "name": exhibitor.name,
                "expo_name": exhibitor.expo_name,
                "industry": exhibitor.industry,
                "city": exhibitor.city,
            }

    data = {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "application": product.application,
        "price_spec": product.price_spec,
        "image": product.image,
        "exhibitor_name": product.exhibitor_name,
        "expo_name": product.expo_name,
        "exhibitor_id": product.exhibitor_id,
        # ---- 详情额外字段 ----
        "detail_html": product.detail_html,
        "source": product.source,
        "exhibitor": exhibitor_info,
    }
    return _ok(data)


# ============================================================
# 目录统计
# ============================================================

def _distinct_count(db: Session, column, model) -> int:
    """某列的去重计数（忽略 NULL 与空串）"""
    return (
        db.query(func.count(func.distinct(column)))
        .select_from(model)
        .filter(column.isnot(None), column != "")
        .scalar()
        or 0
    )


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """目录规模统计（公开，供名录首页展示）

    口径：industries / cities / expos 取的是**展商表**的去重计数
    （这三个维度是展商属性；展品表的 expo_name 是冗余副本）。
    """
    return _ok({
        "exhibitors": (
            db.query(func.count(CatalogExhibitor.id))
            .select_from(CatalogExhibitor)
            .scalar()
            or 0
        ),
        "products": (
            db.query(func.count(CatalogProduct.id))
            .select_from(CatalogProduct)
            .scalar()
            or 0
        ),
        "expos": _distinct_count(db, CatalogExhibitor.expo_name, CatalogExhibitor),
        "industries": _distinct_count(db, CatalogExhibitor.industry, CatalogExhibitor),
        "cities": _distinct_count(db, CatalogExhibitor.city, CatalogExhibitor),
    })
