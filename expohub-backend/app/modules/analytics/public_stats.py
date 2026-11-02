"""
公开统计路由（Public Stats）

供首页对外展示使用，无需登录即可访问。
广告法合规要求：对外数字必须可验证 —— 这里所有数字都来自数据库实时
COUNT，不允许任何硬编码/估算/兜底数字。

端点：
- GET /stats/public   首页公开统计 + 最近动态（最新展会 / 最新采购需求）

关于日期条件：展会 start_date / end_date 在库里是 String(30)（ISO 8601
字符串，有的带时区 +08:00 / Z，有的不带），SQL 侧按字符串比较不可靠
（'2026-5-1' 与 '2026-05-01'、带不带时区都会导致误判），因此
upcoming_exhibitions 采用 Python 侧解析成 datetime 后再比较。
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.base import get_db
from app.models.catalog import CatalogExhibitor
from app.models.user import User
from app.models.exhibition import Exhibition
from app.models.product import Product
from app.models.procurement import Procurement
from app.models.micro_booth import MicroBooth

router = APIRouter(prefix="/stats", tags=["公开统计"])

# ============================================================
# 公开可见口径（唯一口径，必须与公开列表一致）
# ============================================================
#
# 公开可见 = status 不在 ('draft', 'cancelled') 里 —— 草稿与已取消不对外。
#
# 之所以不再用白名单 ("published", "ongoing")：公开列表 GET /api/exhibitions
# 与 GET /api/procurements 都不按 status 过滤（游客能看到什么，首页就数什么），
# 用白名单会让首页数字小于列表 total（实测 4 vs 5、4 vs 35 的打脸口径）。
# 现在两边同源：首页 exhibitions == 公开展会列表 total；
# 首页 procurements == 公开采购列表 total（采购需求公开就是全部，不过滤 status）。
PUBLIC_HIDDEN_EXHIBITION_STATUS = ("draft", "cancelled")

# 最近动态条数
RECENT_LIMIT = 5


# ============================================================
# 辅助函数
# ============================================================

def _ok(data) -> dict:
    """统一成功响应（与 dashboard.py 保持一致）"""
    return {"success": True, "code": "OK", "message": "获取成功", "data": data}


def _parse_dt(value: Any) -> Optional[datetime]:
    """把库里的时间值（datetime 或 ISO 8601 字符串）解析为带时区的 datetime。

    - 支持 'Z' 结尾（Python 3.10 及以下 fromisoformat 不认）
    - 支持不带时区的字符串（按 UTC 处理，保证可比较）
    - 解析失败返回 None（该条不参与统计，不会凭空产生数字）
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            # 兜底：只取日期部分 'YYYY-MM-DD'
            try:
                dt = datetime.strptime(text[:10], "%Y-%m-%d")
            except ValueError:
                return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso(value: Any) -> Optional[str]:
    """把库里的时间值转成 ISO 字符串（前端据此计算“多久前”）"""
    dt = _parse_dt(value)
    return dt.isoformat() if dt else None


# ============================================================
# 端点
# ============================================================

@router.get("/public")
def get_public_stats(db: Session = Depends(get_db)):
    """首页公开统计 —— 全部为数据库实时计数（无需登录）

    口径：公开可见 = status 不在 ('draft','cancelled') 里，与公开列表完全一致。

    exhibitions           公开可见的展会数（== GET /api/exhibitions 的 total）
    upcoming_exhibitions  上述展会中 start_date >= 今天 的场次
    exhibitors            名录在册展商数（catalog_exhibitors；2026-10-19 起以真实公开名录为准，
                          不再用平台账号数——账号只有演示用的 6 个，会严重低估）
    products              status='published' 的展品数
    procurements          全部采购需求数（== GET /api/procurements 的 total，不按 status 过滤）
    micro_booths          status='active' 的微展位数
    recent                最近 5 条动态：最新发布展会（仅公开可见）+ 最新采购需求，
                          按时间倒序（口径同上：草稿/已取消的展会不出现）
    """
    # ---- 展会（公开可见：排除草稿与已取消） ----
    visible_exhibitions = (
        db.query(Exhibition)
        .filter(Exhibition.status.notin_(PUBLIC_HIDDEN_EXHIBITION_STATUS))
        .all()
    )
    exhibitions = len(visible_exhibitions)

    # 今天（按服务器本地日期，与用户直觉的“今天”一致）
    today = datetime.now().date()

    # 日期条件在 Python 侧判断：字符串比较不可靠（时区/格式不统一）
    upcoming_exhibitions = 0
    for item in visible_exhibitions:
        start = _parse_dt(item.start_date)
        if start is not None and start.date() >= today:
            upcoming_exhibitions += 1

    # ---- 展商账号 ----
    exhibitors = (
        db.query(func.count(CatalogExhibitor.id)).scalar()
    ) or 0

    # ---- 展品 ----
    products = (
        db.query(func.count(Product.id))
        .filter(Product.status == "published")
        .scalar()
    ) or 0

    # ---- 采购需求（公开即全部） ----
    # 公开列表 GET /api/procurements 不按 status 过滤，因此这里也不过滤：
    # 若只算 pending，首页数字会远小于列表 total（实测 4 vs 35）。
    procurements = (
        db.query(func.count(Procurement.id))
        .scalar()
    ) or 0

    # ---- 微展位 ----
    micro_booths = (
        db.query(func.count(MicroBooth.id))
        .filter(MicroBooth.status == "active")
        .scalar()
    ) or 0

    # ---- 最近动态：最新发布展会 + 最新采购需求，合并后按时间倒序取前 5 ----
    # 用 (解析后的时间, 展示项) 元组排序，避免依赖字符串格式
    merged: List[Tuple[Optional[datetime], Dict[str, Any]]] = []

    # 展会条目同样只取公开可见的：草稿 / 已取消不得出现在首页“实时动态”里，
    # 与上方 exhibitions 计数复用同一口径（PUBLIC_HIDDEN_EXHIBITION_STATUS）。
    # 采购需求条目保持现状：公开列表不过滤 status，动态与之一致。
    recent_exhibitions = (
        db.query(Exhibition)
        .filter(Exhibition.status.notin_(PUBLIC_HIDDEN_EXHIBITION_STATUS))
        .order_by(Exhibition.created_at.desc())
        .limit(RECENT_LIMIT)
        .all()
    )
    for e in recent_exhibitions:
        merged.append((
            _parse_dt(e.created_at),
            {"type": "exhibition", "title": e.title, "at": _iso(e.created_at)},
        ))

    # 2026-10-19：采购需求模块暂无真实数据（原 35 条为 seed，已清空），
    # 动态改取「最新上架展品」，仍是真实数据（products 表）
    recent_products = (
        db.query(Product)
        .filter(Product.status == "published")
        .order_by(Product.id.desc())
        .limit(RECENT_LIMIT)
        .all()
    )
    for p in recent_products:
        merged.append((
            _parse_dt(p.created_at),
            {"type": "product", "title": p.name, "at": _iso(p.created_at)},
        ))

    # 时间缺失的排在最后，其余按时间倒序
    merged.sort(
        key=lambda pair: pair[0] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    recent = [item for _, item in merged[:RECENT_LIMIT]]

    return _ok({
        "exhibitions": exhibitions,
        "upcoming_exhibitions": upcoming_exhibitions,
        "exhibitors": exhibitors,
        "products": products,
        "procurements": procurements,
        "micro_booths": micro_booths,
        "recent": recent,
    })
