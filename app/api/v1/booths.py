"""展位 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_exhibitor, require_organizer, require_any_user
from app.database.session import get_db
from app.schemas.booth import BoothBookRequest, BoothCreate, BoothResponse, BoothUpdate
from app.schemas.common import ApiResponse, PaginatedResponse
from app.services.booth_service import (
    book_booth,
    create_booth,
    get_booth_by_id,
    get_booths_by_exhibition,
    update_booth,
)

router = APIRouter(prefix="/booths", tags=["展位"])


@router.get("/", response_model=ApiResponse[PaginatedResponse[BoothResponse]])
async def list_booths(
    exhibition_id: int = None,
    status: str = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """获取展位列表（公开）"""
    booths, total = get_booths_by_exhibition(
        db, exhibition_id=exhibition_id, status=status,
        page=page, page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    return ApiResponse(data=PaginatedResponse(
        items=[BoothResponse.model_validate(b) for b in booths],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ))


@router.get("/{booth_id}", response_model=ApiResponse[BoothResponse])
async def get_booth(
    booth_id: int,
    db: Session = Depends(get_db),
):
    """获取展位详情（公开）"""
    booth = get_booth_by_id(db, booth_id)
    return ApiResponse(data=BoothResponse.model_validate(booth))


@router.post("/", response_model=ApiResponse[BoothResponse], status_code=201)
async def create_new_booth(
    data: BoothCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_organizer),
):
    """创建展位（主办方）"""
    booth = create_booth(db, data)
    return ApiResponse(data=BoothResponse.model_validate(booth))


@router.put("/{booth_id}", response_model=ApiResponse[BoothResponse])
async def update_existing_booth(
    booth_id: int,
    data: BoothUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_organizer),
):
    """更新展位（主办方）"""
    booth = update_booth(db, booth_id, data)
    return ApiResponse(data=BoothResponse.model_validate(booth))


@router.post("/book", response_model=ApiResponse[BoothResponse])
async def book_existing_booth(
    data: BoothBookRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_exhibitor),
):
    """预订展位（展商）"""
    booth = book_booth(db, data.booth_id, current_user.id)
    return ApiResponse(data=BoothResponse.model_validate(booth))
