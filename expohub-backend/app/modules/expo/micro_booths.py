"""
V2.0: 微展位 API

端点：
- GET    /micro-booths              公开列表
- GET    /micro-booths/my           我的微展位
- GET    /micro-booths/{id}         微展位详情(含展品)
- POST   /micro-booths              创建(exhibitor)
- PUT    /micro-booths/{id}         编辑
- POST   /micro-booths/{id}/products       添加展品(检查会员限额)
- DELETE /micro-booths/{id}/products/{pid} 移除展品
- POST   /micro-booths/{id}/upgrade        升级会员
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.base import get_db
from app.models.exhibition import Exhibition
from app.models.user import User
from app.models.micro_booth import MicroBooth
from app.models.membership import Membership, TIER_PRODUCT_LIMITS
from app.models.product import Product
# 展商名录 / 展品库（只读快照）：名录来源微展位的展品从这里取，不碰平台 products
from app.models.catalog import CatalogExhibitor, CatalogProduct
from app.core.deps import get_current_active_user
from app.core.exceptions import NotFound, Forbidden, BadRequest, Conflict

router = APIRouter(prefix="/micro-booths", tags=["微展位"])

# 名录来源微展位一次最多展示的展品条数（与 catalog 展商详情一致）
CATALOG_PRODUCT_LIMIT = 12


# ============================================================
# Pydantic Schemas
# ============================================================

class MicroBoothCreate(BaseModel):
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    industry_domain: Optional[str] = None


class MicroBoothUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    industry_domain: Optional[str] = None


class AddProductRequest(BaseModel):
    product_id: int


class UpgradeRequest(BaseModel):
    tier: str  # regular / flagship


# ============================================================
# 辅助函数
# ============================================================

def _mb_to_dict(mb: MicroBooth, product_count: int = 0, db: Optional[Session] = None) -> dict:
    # V3.4: 所属展会信息
    exhibition_info = None
    if mb.exhibition_id is not None and db is not None:
        from app.models.exhibition import Exhibition
        exh = db.query(Exhibition).filter(Exhibition.id == mb.exhibition_id).first()
        if exh:
            exhibition_info = {
                "id": exh.id,
                "title": exh.title,
                "status": exh.status,
                "start_date": exh.start_date,
                "end_date": exh.end_date,
                "location": exh.location,
            }
    return {
        "id": mb.id,
        "exhibitor_id": mb.exhibitor_id,
        "name": mb.name,
        "description": mb.description,
        "logo_url": mb.logo_url,
        "industry_domain": mb.industry_domain,
        "membership_tier": mb.membership_tier,
        "product_limit": TIER_PRODUCT_LIMITS.get(mb.membership_tier, 3),
        "product_count": product_count,
        "view_count": mb.view_count,
        "search_appearances": mb.search_appearances,
        "favorite_count": mb.favorite_count,
        "status": mb.status,
        "exhibition_id": mb.exhibition_id,
        "exhibition_info": exhibition_info,  # V3.4: 所属展会(标题/时间/地点/状态)
        "created_at": mb.created_at.isoformat() if mb.created_at else None,
        "updated_at": mb.updated_at.isoformat() if mb.updated_at else None,
    }


def _product_to_dict(p: Product) -> dict:
    images = None
    if p.images:
        try: images = json.loads(p.images)
        except: images = []
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "category": p.category, "price": p.price, "unit": p.unit,
        "images": images, "stock": p.stock, "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _category_suggestions(search: str, limit: int = 5) -> list[str]:
    """把关键词映射到标准品类，返回同父组品类名（供前端「试试这些品类」提示）

    映射规则：关键词是品类名的一部分（如「照明灯」→ 照明），
    或品类名是关键词的一部分（如「电子及家电批发」→ 电子及家电）。
    命中后取该品类所属父组下的全部品类（命中的品类本身排在最前），
    无法映射到任何品类时返回空数组。
    """
    from app.models.category import EXHIBITION_CATEGORIES, get_parent_group

    # 空关键词是任何字符串的子串，必须先拦掉
    if not search:
        return []

    matched = [c for c in EXHIBITION_CATEGORIES if search in c or c in search]
    if not matched:
        return []

    out: list[str] = []
    for cat in matched:
        pg = get_parent_group(cat)
        # 同父组品类；父组缺失时退化为只有命中品类本身
        group = [c for c in EXHIBITION_CATEGORIES if pg and get_parent_group(c) == pg] or [cat]
        for c in group:
            if c not in out:
                out.append(c)
    return out[:limit]


def _check_product_limit(db: Session, micro_booth_id: int) -> int:
    """检查当前微展位已挂展品数，返回当前数量"""
    count = db.query(func.count(Product.id)).filter(
        Product.micro_booth_id == micro_booth_id
    ).scalar() or 0
    return count


def _catalog_product_counts(db: Session, catalog_ids: list[int]) -> dict[int, int]:
    """批量取名录展商的展品数：一条 IN 查询，返回 {catalog_exhibitor_id: product_count}

    名录微展位的「展品数」直接用 catalog_exhibitors.product_count（导入时算好的统计列），
    不逐条 COUNT catalog_products（3 万家 × 列表 20 条会是 20 次查询）。
    不存在的 id 不会出现在返回值里，调用方按 0 处理。
    """
    if not catalog_ids:
        return {}
    rows = (
        db.query(CatalogExhibitor.id, CatalogExhibitor.product_count)
        .filter(CatalogExhibitor.id.in_(catalog_ids))
        .all()
    )
    return {row.id: (row.product_count or 0) for row in rows}


def _catalog_products(
    db: Session, catalog_exhibitor_id: int, limit: int = CATALOG_PRODUCT_LIMIT
) -> list[dict]:
    """取名录展商的名录展品，映射成前端已有的展品结构

    只 SELECT 展示需要的列（detail_html 是大字段，不进 SELECT）；
    排序 `id ASC`，与 app/modules/catalog/routes.py 展商详情的口径一致。
    """
    rows = (
        db.query(
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
        .filter(CatalogProduct.exhibitor_id == catalog_exhibitor_id)
        .order_by(CatalogProduct.id.asc())
        .limit(limit)
        .all()
    )
    return [
        {
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
        for row in rows
    ]


def _catalog_product_total(db: Session, catalog_exhibitor_id: int, shown: int) -> int:
    """名录展商在 catalog 里的展品总数

    口径：优先用 catalog_exhibitors.product_count（与列表卡片同源，避免每次 COUNT）。
    该列来自第三方「展品数量」，实测存在与 catalog_products 行数不一致的情况
    （偏大 / 偏小 / 为 0），因此当它小于本次实际展示条数时用实际 COUNT 兜底，
    保证 limit_info.total >= shown，不出现「12/0」这种自相矛盾的数字。
    """
    row = (
        db.query(CatalogExhibitor.product_count)
        .filter(CatalogExhibitor.id == catalog_exhibitor_id)
        .first()
    )
    total = int((row.product_count if row else 0) or 0)
    if total >= shown:
        return total
    actual = (
        db.query(func.count(CatalogProduct.id))
        .filter(CatalogProduct.exhibitor_id == catalog_exhibitor_id)
        .scalar()
        or 0
    )
    return max(actual, shown)


def _ensure_membership(db: Session, user_id: int) -> Membership:
    """确保展商有会员记录，没有则创建免费会员"""
    m = db.query(Membership).filter(Membership.user_id == user_id).first()
    if not m:
        m = Membership(user_id=user_id, tier="free", product_limit=3)
        db.add(m)
        db.flush()
    return m


# ============================================================
# 端点
# ============================================================

@router.get("")
def list_public(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    industry_domain: Optional[str] = Query(default=None),
    exhibition_id: Optional[int] = Query(default=None, description="V3.4: 按所属展会筛选"),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """公开微展位列表

    搜索语义：名称/行业/简介任一精确包含即命中；命中为 0 时返回空列表（total=0），
    并通过 suggestions 给出可尝试的同父组品类，前端据此展示「没有匹配…」空态。
    """
    q = db.query(MicroBooth).filter(MicroBooth.status == "active")
    if industry_domain:
        q = q.filter(MicroBooth.industry_domain == industry_domain)
    if exhibition_id:
        q = q.filter(MicroBooth.exhibition_id == exhibition_id)
    suggestions: list[str] = []
    matched = True
    if search:
        # 关键词能映射到标准品类时给出同父组品类名，否则为空数组（前端空态据此提示「试试这些品类」）
        suggestions = _category_suggestions(search)
        # 精确匹配：名称 / 行业 / 简介任一命中
        exact = q.filter(
            MicroBooth.name.ilike(f"%{search}%") |
            MicroBooth.industry_domain.ilike(f"%{search}%") |
            MicroBooth.description.ilike(f"%{search}%")
        )
        if exact.count() > 0:
            q = exact
        else:
            # 精确命中为 0 时返回空列表，不再兜底返回全表
            # （此前兜底会让前端「没有匹配」空态永远走不到，表现为「搜什么都一样」）
            matched = False
    if matched:
        total = q.count()
    else:
        total = 0
    from sqlalchemy import case
    # 排序：会员等级优先（旗舰→普通→免费），同级再按更新时间倒序（与浏览量无关）
    tier_order = case(
        (MicroBooth.membership_tier == 'flagship', 1),
        (MicroBooth.membership_tier == 'regular', 2),
        else_=3
    )
    if matched:
        items = q.order_by(tier_order, MicroBooth.updated_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    else:
        items = []

    # 名录来源微展位：展品数走 catalog_exhibitors.product_count，一条 IN 批量查询（无 N+1）
    catalog_ids = sorted({
        mb.catalog_exhibitor_id for mb in items if mb.catalog_exhibitor_id is not None
    })
    catalog_counts = _catalog_product_counts(db, catalog_ids)

    result = []
    for mb in items:
        if mb.catalog_exhibitor_id is not None:
            # 名录微展位：展品数=名录统计列（不查平台 products）
            count = catalog_counts.get(mb.catalog_exhibitor_id, 0)
        else:
            # 平台自建微展位：沿用原逻辑（统计挂在本微展位下的 products）
            count = _check_product_limit(db, mb.id)
        result.append(_mb_to_dict(mb, count, db))

    return {
        "success": True, "code": "OK", "message": "获取成功",
        "data": {"list": result, "total": total, "page": page, "pageSize": page_size,
                 "totalPages": (total + page_size - 1)//page_size if page_size > 0 else 0,
                 "suggestions": suggestions},
    }


@router.get("/facets")
def get_facets(db: Session = Depends(get_db)):
    """微展位广场的分类与展会分面（真实数据统计，替代前端写死的 18 个旧品类）

    2026-10-19：微展位数据来自公开名录后，行业是「医疗器械制造 / 机床工具 / 光电」这类
    名录口径的值，前端原来写死的「电子及家电 / 照明 …」标签点了必然 0 条，
    这里按真实 industry_domain 聚合返回，前端直接渲染。
    """
    rows = (
        db.query(MicroBooth.industry_domain, func.count(MicroBooth.id))
        .filter(
            MicroBooth.status == "active",
            MicroBooth.industry_domain.isnot(None),
            MicroBooth.industry_domain != "",
        )
        .group_by(MicroBooth.industry_domain)
        .order_by(func.count(MicroBooth.id).desc())
        .limit(40)
        .all()
    )
    industries = [{"value": name, "count": count} for name, count in rows]

    expo_rows = (
        db.query(MicroBooth.exhibition_id, Exhibition.title, func.count(MicroBooth.id))
        .join(Exhibition, MicroBooth.exhibition_id == Exhibition.id)
        .filter(MicroBooth.status == "active", Exhibition.status.notin_(("draft", "cancelled")))
        .group_by(MicroBooth.exhibition_id)
        .order_by(func.count(MicroBooth.id).desc())
        .limit(30)
        .all()
    )
    exhibitions = [{"id": eid, "name": title, "count": count} for eid, title, count in expo_rows]

    return {
        "success": True, "code": "OK", "message": "获取成功",
        "data": {"industries": industries, "exhibitions": exhibitions},
    }


@router.get("/my")
def my_booths(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """我的微展位列表"""
    items = db.query(MicroBooth).filter(
        MicroBooth.exhibitor_id == current_user.id
    ).order_by(MicroBooth.created_at.desc()).all()

    result = []
    for mb in items:
        count = _check_product_limit(db, mb.id)
        result.append(_mb_to_dict(mb, count, db))

    return {"success": True, "code": "OK", "message": "获取成功", "data": result}


@router.get("/{mb_id}")
def get_detail(mb_id: int, db: Session = Depends(get_db)):
    """微展位详情(含展品列表)，按会员等级限制展品数

    名录来源微展位（catalog_exhibitor_id 非空）：展品从 catalog_products 取（只读快照），
    一次取 12 条，total 用名录展品总数，upgrade_hint=None（名录展品不涉及会员限额）。
    平台自建微展位：沿用原逻辑（平台 products + 会员等级限额）。
    """
    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")

    # ---- 名录来源：展品来自 catalog_products ----
    if mb.catalog_exhibitor_id is not None:
        catalog_products = _catalog_products(db, mb.catalog_exhibitor_id)
        catalog_total = _catalog_product_total(
            db, mb.catalog_exhibitor_id, len(catalog_products)
        )
        return {
            "success": True, "code": "OK", "message": "获取成功",
            "data": {
                "booth": _mb_to_dict(mb, catalog_total, db),
                "products": catalog_products,
                "limit_info": {
                    "tier": mb.membership_tier,
                    "limit": CATALOG_PRODUCT_LIMIT,
                    "total": catalog_total,
                    "shown": len(catalog_products),
                    "upgrade_hint": None,
                },
            },
        }

    # ---- 平台自建微展位：原逻辑不变 ----
    limit = TIER_PRODUCT_LIMITS.get(mb.membership_tier, 3)
    total_products = db.query(Product).filter(
        Product.micro_booth_id == mb_id
    ).count()

    products = db.query(Product).filter(
        Product.micro_booth_id == mb_id
    ).order_by(Product.created_at.desc())
    if limit > 0:  # 0 = flagship unlimited
        products = products.limit(limit)
    products = products.all()

    return {
        "success": True, "code": "OK", "message": "获取成功",
        "data": {
            "booth": _mb_to_dict(mb, total_products, db),
            "products": [_product_to_dict(p) for p in products],
            "limit_info": {
                "tier": mb.membership_tier,
                "limit": limit,
                "total": total_products,
                "shown": len(products),
                "upgrade_hint": f"已展示{len(products)}/{total_products}个展品，升级会员展示全部" if limit > 0 and total_products > limit else None,
            }
        },
    }


@router.post("")
def create_booth(
    data: MicroBoothCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """创建微展位（展商）"""
    if current_user.role not in ("exhibitor", "admin"):
        raise Forbidden(message="仅展商可创建微展位")

    # 确保有会员记录
    _ensure_membership(db, current_user.id)

    mb = MicroBooth(
        exhibitor_id=current_user.id,
        name=data.name,
        description=data.description,
        logo_url=data.logo_url,
        industry_domain=data.industry_domain or current_user.industry_domain,
        membership_tier="free",
    )
    db.add(mb)
    db.commit()
    db.refresh(mb)

    return {"success": True, "code": "OK", "message": "微展位创建成功", "data": _mb_to_dict(mb, 0, db)}


@router.put("/{mb_id}")
def update_booth(
    mb_id: int,
    data: MicroBoothUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """编辑微展位"""
    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")
    if mb.exhibitor_id != current_user.id and current_user.role != "admin":
        raise Forbidden(message="无权编辑此微展位")

    updates = data.model_dump(exclude_unset=True)
    for k, v in updates.items():
        if hasattr(mb, k):
            setattr(mb, k, v)
    db.commit()
    db.refresh(mb)

    count = _check_product_limit(db, mb.id)
    return {"success": True, "code": "OK", "message": "更新成功", "data": _mb_to_dict(mb, count, db)}


@router.post("/{mb_id}/products")
def add_product(
    mb_id: int,
    data: AddProductRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """向微展位添加展品（检查会员限额）"""
    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")
    if mb.exhibitor_id != current_user.id:
        raise Forbidden(message="无权操作此微展位")

    # 检查限额
    limit = TIER_PRODUCT_LIMITS.get(mb.membership_tier, 3)
    current_count = _check_product_limit(db, mb.id)
    if limit > 0 and current_count >= limit:
        raise BadRequest(
            message=f"当前{mb.membership_tier}会员最多可挂{limit}个展品，已用{current_count}个。请升级会员以添加更多展品"
        )

    # 检查展品是否属于当前用户
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise NotFound(message="展品不存在")
    if product.exhibitor_id != current_user.id:
        raise Forbidden(message="无权操作此展品")

    product.micro_booth_id = mb_id
    db.commit()

    count = _check_product_limit(db, mb.id)
    return {"success": True, "code": "OK", "message": "展品已添加到微展位", "data": _mb_to_dict(mb, count, db)}


@router.delete("/{mb_id}/products/{product_id}")
def remove_product(
    mb_id: int, product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """从微展位移除展品"""
    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")
    if mb.exhibitor_id != current_user.id:
        raise Forbidden(message="无权操作此微展位")

    product = db.query(Product).filter(
        Product.id == product_id, Product.micro_booth_id == mb_id
    ).first()
    if not product:
        raise NotFound(message="该展品未挂在此微展位")

    product.micro_booth_id = None
    db.commit()
    return {"success": True, "code": "OK", "message": "展品已移除", "data": None}


@router.post("/{mb_id}/upgrade")
def upgrade_membership(
    mb_id: int,
    data: UpgradeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """升级会员等级"""
    if data.tier not in ("regular", "flagship"):
        raise BadRequest(message="无效的会员等级，可选: regular, flagship")

    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")
    if mb.exhibitor_id != current_user.id:
        raise Forbidden(message="无权操作")

    old_tier = mb.membership_tier
    mb.membership_tier = data.tier

    # 更新会员记录
    membership = _ensure_membership(db, current_user.id)
    membership.tier = data.tier
    membership.product_limit = TIER_PRODUCT_LIMITS[data.tier]

    db.commit()
    db.refresh(mb)

    count = _check_product_limit(db, mb.id)
    return {
        "success": True, "code": "OK",
        "message": f"已从 {old_tier} 升级为 {data.tier}",
        "data": _mb_to_dict(mb, count, db),
    }


@router.delete("/{mb_id}")
def delete_booth(
    mb_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """删除微展位"""
    mb = db.query(MicroBooth).filter(MicroBooth.id == mb_id).first()
    if not mb:
        raise NotFound(message="微展位不存在")
    if mb.exhibitor_id != current_user.id and current_user.role != "admin":
        raise Forbidden(message="无权删除此微展位")
    # 清除关联展品的 micro_booth_id
    from app.models.product import Product
    db.query(Product).filter(Product.micro_booth_id == mb_id).update({"micro_booth_id": None})
    db.delete(mb)
    db.commit()
    return {"success": True, "code": "OK", "message": "微展位已删除", "data": None}
