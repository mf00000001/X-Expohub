"""展会 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_any_user, require_boss, require_organizer, require_staff
from app.database.session import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.exhibition import (
    ExhibitionCreate,
    ExhibitionListParams,
    ExhibitionResponse,
    ExhibitionUpdate,
)
from app.services import exhibition_service

router = APIRouter(prefix="/exhibitions", tags=["展会"])


@router.get("/", response_model=ApiResponse[PaginatedResponse[ExhibitionResponse]])
async def list_exhibitions(
    params: ExhibitionListParams = Depends(),
    db: Session = Depends(get_db),
):
    """获取展会列表（公开）"""
    exhibitions, total = exhibition_service.get_exhibition_list(
        db,
        page=params.page,
        page_size=params.page_size,
        city=params.city,
        status=params.status or "published",
        keyword=params.keyword,
    )
    total_pages = (total + params.page_size - 1) // params.page_size
    return ApiResponse(data=PaginatedResponse(
        items=[ExhibitionResponse.model_validate(e) for e in exhibitions],
        total=total,
        page=params.page,
        page_size=params.page_size,
        total_pages=total_pages,
    ))


@router.get("/{exhibition_id}", response_model=ApiResponse[ExhibitionResponse])
async def get_exhibition(
    exhibition_id: int,
    db: Session = Depends(get_db),
):
    """获取展会详情（公开）"""
    exhibition = exhibition_service.get_exhibition_by_id(db, exhibition_id)
    return ApiResponse(data=ExhibitionResponse.model_validate(exhibition))


@router.post("/", response_model=ApiResponse[ExhibitionResponse], status_code=201)
async def create_exhibition(
    data: ExhibitionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_organizer),
):
    """创建展会（主办方）"""
    exhibition = exhibition_service.create_exhibition(db, current_user.id, data)
    return ApiResponse(data=ExhibitionResponse.model_validate(exhibition))


@router.put("/{exhibition_id}", response_model=ApiResponse[ExhibitionResponse])
async def update_exhibition(
    exhibition_id: int,
    data: ExhibitionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_organizer),
):
    """更新展会（主办方）"""
    exhibition = exhibition_service.update_exhibition(
        db, exhibition_id, current_user.id, data
    )
    return ApiResponse(data=ExhibitionResponse.model_validate(exhibition))


@router.post("/{exhibition_id}/publish", response_model=ApiResponse[ExhibitionResponse])
async def publish_exhibition(
    exhibition_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_organizer),
):
    """发布展会（提交审批，主办方）"""
    exhibition = exhibition_service.publish_exhibition(db, exhibition_id, current_user.id)
    return ApiResponse(data=ExhibitionResponse.model_validate(exhibition))


@router.post("/{exhibition_id}/approve", response_model=ApiResponse[ExhibitionResponse])
async def approve_exhibition(
    exhibition_id: int,
    approved: bool = True,
    reject_reason: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_boss),
):
    """审批展会（老板）"""
    exhibition = exhibition_service.approve_exhibition(
        db, exhibition_id, current_user.id, approved, reject_reason
    )
    return ApiResponse(data=ExhibitionResponse.model_validate(exhibition))


@router.get("/organizer/list", response_model=ApiResponse[PaginatedResponse[ExhibitionResponse]])
async def list_my_exhibitions(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_organizer),
):
    """获取主办方自己的展会列表"""
    exhibitions, total = exhibition_service.get_exhibition_list(
        db,
        page=page,
        page_size=page_size,
        status=status,
        organizer_id=current_user.id,
    )
    total_pages = (total + page_size - 1) // page_size
    return ApiResponse(data=PaginatedResponse(
        items=[ExhibitionResponse.model_validate(e) for e in exhibitions],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ))
