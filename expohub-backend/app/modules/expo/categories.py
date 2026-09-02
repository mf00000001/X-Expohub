"""
Categories API endpoint — returns the standardized Canton Fair 16+2 category list.
"""

from fastapi import APIRouter
from app.models.category import (
    EXHIBITION_CATEGORIES,
    CATEGORY_PARENT_GROUPS,
    PARENT_GROUP_CATEGORIES,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
async def list_categories():
    """
    Return the full standard category list with parent group information.
    """
    return {
        "categories": EXHIBITION_CATEGORIES,
        "parent_groups": CATEGORY_PARENT_GROUPS,
        "grouped": PARENT_GROUP_CATEGORIES,
    }


@router.get("/groups")
async def list_parent_groups():
    """
    Return only the parent groups with their subcategories.
    """
    return {"groups": PARENT_GROUP_CATEGORIES}
