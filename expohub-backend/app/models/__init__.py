"""
ExpoHub 数据模型包

所有 SQLAlchemy SQLite 数据模型。
表名和字段名与前端 API (expo-hub-uniapp/src/api/) 的 TypeScript 接口完全一致。
"""

from app.models.base import Base, engine, get_db, SessionLocal

# 用户
from app.models.user import User

# 展会
from app.models.exhibition import Exhibition

# 展位
from app.models.booth import Booth

# 展品
from app.models.product import Product

# 采购需求
from app.models.procurement import Procurement
from app.models.procurement_match import ProcurementMatch

# 消息 & 会话
from app.models.message import Message, Conversation

# 评价
from app.models.review import Review

# 报名
from app.models.registration import Registration

# 展商名录 / 展品库（第三方公开名录快照，只读）
from app.models.catalog import CatalogExhibitor, CatalogProduct

# 参展关系（展会 ↔ 名录展商，多对多；替代 catalog_exhibitors.exhibition_id 弱关联）
from app.models.exhibition_exhibitor import ExhibitionExhibitor

__all__ = [
    "Base",
    "engine",
    "get_db",
    "SessionLocal",
    "User",
    "Exhibition",
    "Booth",
    "Product",
    "Procurement",
    "ProcurementMatch",
    "Message",
    "Conversation",
    "Review",
    "Registration",
    "CatalogExhibitor",
    "CatalogProduct",
    "ExhibitionExhibitor",
]
