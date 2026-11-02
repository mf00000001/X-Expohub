"""
全球标杆展会（Hall of Fame）—— 首页「人工精选」静态配置

背景
----
产品要求首页固定展示全球不超过 10 个标杆展会作为引流抓手。这批内容是
**编辑精选**（人工维护），不是从数据库里按规模/热度筛出来的：库里展会只有
几场，且随用户录入不断变化；一旦「精选」跟着库走，首页当天展示什么就不可控。

因此做成后端静态配置：
- 数据内置于本模块常量 HALL_OF_FAME，顺序即首页展示顺序；
- 接口不查数据库、不依赖登录，任何情况下都能稳定返回（库空、库挂都一样）；
- 后续若由管理员维护，只需替换数据来源（改常量 / 换成配置表），
  接口契约（路径、字段、结构）保持不变，前端无需改动。

端点
----
- GET /api/exhibitions/hall-of-fame   公开，无需登录

字段说明
--------
id          英文 slug（前端可用作稳定 key，不随库内展会 id 变化）
name        展会全称
short_name  通用简称（境外展会取其国际通用名）
city        举办城市
country     举办国家
tagline     一句中文卖点（≤ 24 字，具体、不夸张）
sector      所属行业
edition     举办频次（固定信息，不写具体日期，避免过时）

文案口径（合规）
----------------
- tagline 只写可长期成立的信息：受众、规模量级、行业地位等可核事实；
- 不使用绝对化用语（排名类、极限化形容词一类），避免广告法风险；
- edition 只写「每年一届 / 两年一届 / 每年春秋两届」这类频次，
  不写具体日期与届次（每年都会变，写死即过时）。
"""

from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter(prefix="/exhibitions", tags=["全球标杆展会"])

# 精选条数上限：产品要求「全球不超过 10 个」，增删条目时请同步检查本约束。
HALL_OF_FAME_LIMIT = 10

# 精选数据（顺序即首页展示顺序：列表开头先展示，不做任何排序）。
# 10 条均为真实存在的展会，按「中国 + 海外」分组排列，便于人工维护与审阅。
import json
from pathlib import Path

_DIRECTORY_FILE = Path(__file__).resolve().parents[3] / "data" / "exhibition_directory.json"


def _load_directory() -> list:
    """读取 data/exhibition_directory.json（由「重点展会清单(30+)」导出，48 条真实展会资料）"""
    try:
        with open(_DIRECTORY_FILE, encoding="utf-8") as fh:
            items = json.load(fh)
        return items if isinstance(items, list) else []
    except (OSError, ValueError):
        return []


_DIRECTORY = _load_directory()

# 首页固定展示的前 10 个（顺序即展示顺序）
HALL_OF_FAME: List[Dict[str, str]] = [
    {
        "id": it.get("id") or "",
        "name": it.get("name") or "",
        "short_name": it.get("short_name") or it.get("name") or "",
        "city": it.get("city") or "",
        "country": it.get("country") or "中国",
        "sector": it.get("sector") or "",
        "edition": it.get("edition") or "",
        # 卖点直接使用真实规模（如「约3.2万展商/155万㎡」），缺省退化为「行业 · 档期」
        "tagline": it.get("scale") or " · ".join(x for x in (it.get("sector"), it.get("schedule")) if x),
        "organizer": it.get("organizer") or "",
        "schedule": it.get("schedule") or "",
    }
    for it in _DIRECTORY[:HALL_OF_FAME_LIMIT]
]


def _ok(data: Any) -> dict:
    """统一成功响应（与 analytics/public_stats.py、dashboard.py 保持同一信封）"""
    return {"success": True, "code": "OK", "message": "获取成功", "data": data}


def get_hall_of_fame_list() -> List[Dict[str, str]]:
    """返回精选列表的逐条浅拷贝。

    拷贝是为了防止调用方（或测试）就地修改返回结果污染模块内常量：
    常量一旦被改，后续所有请求都会看到被改过的数据。
    """
    return [dict(item) for item in HALL_OF_FAME]


@router.get("/hall-of-fame")
def get_hall_of_fame() -> dict:
    """获取全球标杆展会（首页人工精选；公开接口，无需登录）

    设计约束：
    - 不查数据库：纯静态配置，库内数据增删改都不影响本接口；
    - 不依赖登录：没有登录依赖，游客直接可访问；
    - total == len(list)：两者由同一份数据算出，不存在口径不一致；
    - 顺序即展示顺序：不做排序、不做筛选。
    """
    items = get_hall_of_fame_list()
    return _ok({"list": items, "total": len(items)})
