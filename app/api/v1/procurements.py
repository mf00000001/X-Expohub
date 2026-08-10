"""采购需求 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_exhibitor, require_visitor, require_any_user
from app.database.session import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.procurement import (
    MatchCreate,
    MatchResponse,
    ProcurementCreate,
    ProcurementResponse,
    ProcurementUpdate,
)
from app.services import procurement_service

router = APIRouter(prefix="/procurements", tags=["采购需求"])


@router.post("/", response_model=ApiResponse[ProcurementResponse], status_code=201)
async def create_procurement(
    data: ProcurementCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_visitor),
):
    """发布采购需求（游客）"""
    procurement = procurement_service.create_procurement(db, current_user.id, data)
    return ApiResponse(data=ProcurementResponse.model_validate(procurement))


@router.get("/", response_model=ApiResponse[PaginatedResponse[ProcurementResponse]])
async def list_procurements(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    category: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_user),
):
    """获取采购需求列表"""
    procurements, total = procurement_service.get_procurement_list(
        db, page=page, page_size=page_size,
        status=status, category=category,
    )
    total_pages = (total + page_size - 1) // page_size
    return ApiResponse(data=PaginatedResponse(
        items=[ProcurementResponse.model_validate(p) for p in procurements],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ))


@router.get("/my", response_model=ApiResponse[PaginatedResponse[ProcurementResponse]])
async def list_my_procurements(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_visitor),
):
    """获取我的采购需求列表（游客）"""
    procurements, total = procurement_service.get_procurement_list(
        db, page=page, page_size=page_size,
        status=status, visitor_id=current_user.id,
    )
    total_pages = (total + page_size - 1) // page_size
    return ApiResponse(data=PaginatedResponse(
        items=[ProcurementResponse.model_validate(p) for p in procurements],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ))


@router.get("/{procurement_id}", response_model=ApiResponse[ProcurementResponse])
async def get_procurement(
    procurement_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_user),
):
    """获取采购需求详情"""
    procurement = procurement_service.get_procurement_by_id(db, procurement_id)
    return ApiResponse(data=ProcurementResponse.model_validate(procurement))


@router.put("/{procurement_id}", response_model=ApiResponse[ProcurementResponse])
async def update_procurement(
    procurement_id: int,
    data: ProcurementUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_visitor),
):
    """更新采购需求（游客）"""
    procurement = procurement_service.update_procurement(
        db, procurement_id, current_user.id, data
    )
    return ApiResponse(data=ProcurementResponse.model_validate(procurement))


# 采购匹配
@router.post("/matches", response_model=ApiResponse[MatchResponse], status_code=201)
async def create_match(
    data: MatchCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_exhibitor),
):
    """展商匹配采购需求（展商）"""
    match = procurement_service.create_match(db, current_user.id, data)
    return ApiResponse(data=MatchResponse.model_validate(match))


@router.get("/{procurement_id}/matches", response_model=ApiResponse[list[MatchResponse]])
async def get_procurement_matches(
    procurement_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_any_user),
):
    """获取采购需求的匹配列表"""
    matches = procurement_service.get_matches_for_procurement(db, procurement_id)
    return ApiResponse(data=[MatchResponse.model_validate(m) for m in matches])


@router.post("/matches/{match_id}/accept", response_model=ApiResponse[MatchResponse])
async def accept_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_visitor),
):
    """采购方接受匹配（游客）"""
    match = procurement_service.accept_match(db, match_id, current_user.id)
    return ApiResponse(data=MatchResponse.model_validate(match))
