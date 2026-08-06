"""
ExpoHub standardized category system.
Matches the Canton Fair's 16-category classification plus AI/Tech and Comprehensive Services.
"""

EXHIBITION_CATEGORIES = [
    "电子及家电",
    "照明",
    "车辆及配件",
    "五金工具",
    "机械",
    "建材",
    "化工产品",
    "能源",
    "日用消费品",
    "礼品",
    "纺织服装",
    "鞋类",
    "家居装饰品",
    "办公箱包及休闲用品",
    "食品",
    "医药及医疗保健",
    "AI/科技",
    "综合服务",
]

# Parent group mapping: each parent group contains related subcategories
# This enables hierarchical matching for procurement recommendations
CATEGORY_PARENT_GROUPS = {
    "电子及家电": "电子电器",
    "照明": "电子电器",
    "车辆及配件": "机械装备",
    "五金工具": "机械装备",
    "机械": "机械装备",
    "建材": "建筑装饰",
    "化工产品": "工业原料",
    "能源": "工业原料",
    "日用消费品": "消费品",
    "礼品": "消费品",
    "纺织服装": "纺织鞋服",
    "鞋类": "纺织鞋服",
    "家居装饰品": "建筑装饰",
    "办公箱包及休闲用品": "消费品",
    "食品": "食品医药",
    "医药及医疗保健": "食品医药",
    "AI/科技": "新兴技术",
    "综合服务": "新兴技术",
}

# Reverse mapping: parent group -> list of categories
PARENT_GROUP_CATEGORIES: dict[str, list[str]] = {}
for _cat, _parent in CATEGORY_PARENT_GROUPS.items():
    PARENT_GROUP_CATEGORIES.setdefault(_parent, []).append(_cat)


def get_parent_group(category: str) -> str | None:
    """Return the parent group for a given category."""
    return CATEGORY_PARENT_GROUPS.get(category)


def is_same_parent_group(cat1: str, cat2: str) -> bool:
    """Check if two categories belong to the same parent group."""
    p1 = CATEGORY_PARENT_GROUPS.get(cat1)
    p2 = CATEGORY_PARENT_GROUPS.get(cat2)
    return p1 is not None and p1 == p2


def match_category_score(cat1: str, cat2: str) -> int:
    """
    Compute a matching score between two categories.
    - Exact match: 50 points
    - Same parent group: 30 points
    - Keyword overlap (any shared characters beyond 2): 20 points
    - No match: 0 points
    """
    if cat1 == cat2:
        return 50
    if is_same_parent_group(cat1, cat2):
        return 30
    # Keyword overlap: count shared Chinese characters
    shared = set(cat1) & set(cat2)
    if len(shared) >= 2:
        return 20
    return 0


def validate_category(category: str) -> bool:
    """Check if a category is in the standard list."""
    return category in EXHIBITION_CATEGORIES
