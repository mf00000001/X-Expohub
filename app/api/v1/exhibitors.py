"""展商 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_exhibitor, require_any_user
from app.database.session import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.exhibitor import (
    ExhibitorCreate,
    ExhibitorResponse,
    ExhibitorUpdate,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.services import exhibitor_service

router = APIRouter(prefix="/exhibitors", tags=["展商"])


@router.post("/info", response_model=ApiResponse[ExhibitorResponse], status_code=201)
async def create_exhibitor_info(
    data: ExhibitorCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_exhibitor),
):
    """创建/完善展商信息（展商）"""
    exhibitor = exhibitor_service.create_exhibitor_info(db, current_user.id, data)
    return ApiResponse(data=ExhibitorResponse.model_validate(exhibitor))


@router.get("/info", response_model=ApiResponse[ExhibitorResponse])
async def get_my_exhibitor_info(
    db: Session = Depends(get_db),
    current_user=Depends(require_exhibitor),
):
    """获取我的展商信息（展商）"""
    exhibitor = exhibitor_service.get_exhibitor_info(db, current_user.id)
    return ApiResponse(data=ExhibitorResponse.model_validate(exhibitor))


@router.put("/info", response_model=ApiResponse[ExhibitorResponse])
async def update_exhibitor_info(
    data: ExhibitorUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_exhibitor),
):
    """更新展商信息（展商）"""
    exhibitor = exhibitor_service.update_exhibitor_info(db, current_user.id, data)
    return ApiResponse(data=ExhibitorResponse.model_validate(exhibitor))


# 展品管理
@router.post("/products", response_model=ApiResponse[ProductResponse], status_code=201)
async def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_exhibitor),
):
    """创建展品（展商）"""
    product = exhibitor_service.create_product(db, current_user.id, data)
    return ApiResponse(data=ProductResponse.model_validate(product))


@router.get("/products", response_model=ApiResponse[PaginatedResponse[ProductResponse]])
async def list_my_products(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user=Depends(require_exhibitor),
):
    """获取我的展品列表（展商）"""
    products, total = exhibitor_service.get_products_by_exhibitor(
        db, current_user.id, page, page_size
    )
    total_pages = (total + page_size - 1) // page_size
    return ApiResponse(data=PaginatedResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    ))


@router.put("/products/{product_id}", response_model=ApiResponse[ProductResponse])
async def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_exhibitor),
):
    """更新展品（展商）"""
    product = exhibitor_service.update_product(db, product_id, current_user.id, data)
    return ApiResponse(data=ProductResponse.model_validate(product))


@router.delete("/products/{product_id}", response_model=ApiResponse)
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_exhibitor),
):
    """删除展品（展商）"""
    exhibitor_service.delete_product(db, product_id, current_user.id)
    return ApiResponse(message="展品已删除")
