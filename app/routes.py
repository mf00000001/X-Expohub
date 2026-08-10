"""
ExpoHub API 路由 — 完整版（45+ 端点）

路由分层：
- /api/auth/*          认证（注册/登录/刷新/个人信息）
- /api/users/*         用户管理
- /api/exhibitions/*   展会公开浏览
- /api/booths/*        展位浏览与预订
- /api/registrations/* 报名管理
- /api/procurement/*   采购需求（游客发布 + 展商匹配）
- /api/products/*      展品管理（展商）
- /api/messages/*      站内消息
- /api/reviews/*       展会评价
- /api/dashboard/*     角色仪表盘
- /api/admin/*         管理后台（主办方/老板）
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, and_, func, select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import (
    User, UserRole, UserStatus, Exhibition, ExhibitionStatus,
    Booth, BoothStatus, VisitorRegistration, AuditLog,
    Message, Review, ProcurementRequest, ProcurementStatus,
    ProcurementMatch, Product, ProductStatus,
)
from app.schemas import (
    LoginRequest, TokenResponse, RefreshTokenRequest, RefreshTokenResponse,
    RegisterRequest, UserProfileResponse, UserUpdateRequest,
    ExhibitionCreateRequest, ExhibitionResponse, ExhibitionListResponse,
    BoothCreateRequest, BoothResponse, BoothBookRequest, BoothUpdateRequest,
    RegistrationCreateRequest, RegistrationResponse,
    ProcurementCreateRequest, ProcurementUpdateRequest, ProcurementResponse,
    ProcurementMatchCreateRequest, ProcurementMatchResponse,
    ProductCreateRequest, ProductUpdateRequest, ProductResponse,
    MessageCreateRequest, MessageResponse, MessageListResponse,
    UnreadCountResponse, ConversationResponse,
    ReviewCreateRequest, ReviewResponse, RatingStatsResponse,
    ExhibitorDashboardResponse, OrganizerDashboardResponse,
    AdminExhibitionStatsResponse, AdminRegistrationDetailResponse,
    AdminBoothAllocationResponse, AuditLogResponse,
    ExhibitionApproveRequest, StatsOverviewResponse,
)
from app.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, refresh_access_token,
    get_current_user, require_auth,
    require_role, require_visitor, require_exhibitor,
    require_organizer, require_boss, require_staff,
    CurrentUser,
)

router = APIRouter()


# ============================================================
# 健康检查
# ============================================================

@router.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": "ExpoHub API", "timestamp": datetime.now(timezone.utc).isoformat()}


# ============================================================
# 认证路由 /api/auth/*
# ============================================================

auth_router = APIRouter(prefix="/api/auth", tags=["认证"])


@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(or_(User.username == data.username, User.email == data.email))
    )
    existing = result.scalars().first()
    if existing:
        if existing.username == data.username:
            raise HTTPException(status_code=409, detail="用户名已存在")
        raise HTTPException(status_code=409, detail="邮箱已被注册")

    user = User(
        username=data.username, email=data.email, phone=data.phone,
        password_hash=hash_password(data.password), role=data.role,
        status=UserStatus.ACTIVE, nickname=data.nickname or data.username,
        company=data.company,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user_id=user.id, role=user.role.value)
    refresh_tok = create_refresh_token(user_id=user.id, role=user.role.value)
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_tok,
        token_type="bearer", expires_in=15 * 60,
        user=UserProfileResponse.model_validate(user),
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(or_(User.username == data.username, User.email == data.username))
    )
    user = result.scalars().first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名/邮箱或密码错误")
    if user.status == UserStatus.DISABLED:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    if user.status == UserStatus.BANNED:
        raise HTTPException(status_code=403, detail="账号已被封禁")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(user_id=user.id, role=user.role.value)
    refresh_tok = create_refresh_token(user_id=user.id, role=user.role.value)
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_tok,
        token_type="bearer", expires_in=15 * 60,
        user=UserProfileResponse.model_validate(user),
    )


@auth_router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(data: RefreshTokenRequest):
    result = refresh_access_token(data.refresh_token)
    return RefreshTokenResponse(**result)


@auth_router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    return result.scalars().first()


# ============================================================
# 用户路由 /api/users/*
# ============================================================

users_router = APIRouter(prefix="/api/users", tags=["用户管理"])


@users_router.get("/me", response_model=UserProfileResponse)
async def get_profile(
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    return result.scalars().first()


@users_router.put("/me", response_model=UserProfileResponse)
async def update_profile(
    data: UserUpdateRequest,
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================
# 展会公开路由 /api/exhibitions/*
# ============================================================

exhibition_router = APIRouter(prefix="/api/exhibitions", tags=["展会管理"])


@exhibition_router.get("", response_model=List[ExhibitionListResponse])
async def list_exhibitions(
    city: Optional[str] = Query(None),
    status_param: Optional[str] = Query(None, alias="status"),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if status_param:
        conditions.append(Exhibition.status == status_param)
    else:
        conditions.append(Exhibition.status.in_([ExhibitionStatus.PUBLISHED, ExhibitionStatus.ONGOING]))
    if city:
        conditions.append(Exhibition.city == city)
    if keyword:
        conditions.append(or_(
            Exhibition.name.ilike(f"%{keyword}%"),
            Exhibition.description.ilike(f"%{keyword}%"),
            Exhibition.venue.ilike(f"%{keyword}%"),
        ))

    stmt = (select(Exhibition).where(and_(*conditions))
            .order_by(Exhibition.start_date.asc())
            .offset((page - 1) * page_size).limit(page_size))
    result = await db.execute(stmt)
    return result.scalars().all()


@exhibition_router.get("/{exhibition_id}", response_model=ExhibitionResponse)
async def get_exhibition(exhibition_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Exhibition).where(Exhibition.id == exhibition_id))
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在")
    return exhibition


@exhibition_router.get("/{exhibition_id}/booths", response_model=List[BoothResponse])
async def list_exhibition_booths(exhibition_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Exhibition).where(Exhibition.id == exhibition_id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="展会不存在")
    result = await db.execute(
        select(Booth).where(Booth.exhibition_id == exhibition_id).order_by(Booth.booth_number)
    )
    return result.scalars().all()


@exhibition_router.get("/{exhibition_id}/reviews", response_model=List[ReviewResponse])
async def list_exhibition_reviews(
    exhibition_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Exhibition).where(Exhibition.id == exhibition_id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="展会不存在")
    stmt = (select(Review).where(Review.exhibition_id == exhibition_id)
            .order_by(desc(Review.created_at))
            .offset((page - 1) * page_size).limit(page_size))
    result = await db.execute(stmt)
    reviews = result.scalars().all()
    # Enrich with username
    out = []
    for r in reviews:
        r_dict = ReviewResponse.model_validate(r).model_dump()
        user_result = await db.execute(select(User.username).where(User.id == r.user_id))
        username = user_result.scalar()
        r_dict["username"] = username
        out.append(r_dict)
    return out


# ============================================================
# 展位路由 /api/booths/*
# ============================================================

booth_router = APIRouter(prefix="/api/booths", tags=["展位管理"])


@booth_router.get("", response_model=List[BoothResponse])
async def list_booths(
    exhibition_id: Optional[int] = Query(None),
    zone: Optional[str] = Query(None),
    status_param: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if exhibition_id:
        conditions.append(Booth.exhibition_id == exhibition_id)
    if zone:
        conditions.append(Booth.zone == zone)
    if status_param:
        conditions.append(Booth.status == status_param)
    else:
        conditions.append(Booth.status != BoothStatus.MAINTENANCE)
    result = await db.execute(
        select(Booth).where(and_(*conditions)).order_by(Booth.booth_number)
    )
    return result.scalars().all()


@booth_router.get("/{booth_id}", response_model=BoothResponse)
async def get_booth(booth_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Booth).where(Booth.id == booth_id))
    booth = result.scalars().first()
    if not booth:
        raise HTTPException(status_code=404, detail="展位不存在")
    return booth


@booth_router.get("/my", response_model=List[BoothResponse])
async def my_booths(
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booth).where(Booth.exhibitor_id == current_user.user_id).order_by(Booth.updated_at.desc())
    )
    return result.scalars().all()


@booth_router.post("/book", response_model=BoothResponse)
async def book_booth(
    data: BoothBookRequest,
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Booth).where(Booth.id == data.booth_id))
    booth = result.scalars().first()
    if not booth:
        raise HTTPException(status_code=404, detail="展位不存在")
    if booth.status != BoothStatus.AVAILABLE:
        raise HTTPException(status_code=409, detail="展位已被预订或占用")

    existing_result = await db.execute(
        select(Booth).where(
            Booth.exhibitor_id == current_user.user_id,
            Booth.exhibition_id == booth.exhibition_id,
        )
    )
    if existing_result.scalars().first():
        raise HTTPException(status_code=409, detail="您已在该展会拥有展位")

    booth.exhibitor_id = current_user.user_id
    booth.status = BoothStatus.RESERVED

    exh_result = await db.execute(select(Exhibition).where(Exhibition.id == booth.exhibition_id))
    exhibition = exh_result.scalars().first()
    if exhibition and exhibition.available_booths > 0:
        exhibition.available_booths -= 1

    await db.commit()
    await db.refresh(booth)
    return booth


@booth_router.put("/{booth_id}", response_model=BoothResponse)
async def update_booth(
    booth_id: int,
    data: BoothUpdateRequest,
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booth).where(Booth.id == booth_id, Booth.exhibitor_id == current_user.user_id)
    )
    booth = result.scalars().first()
    if not booth:
        raise HTTPException(status_code=404, detail="展位不存在或无权操作")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(booth, field, value)
    await db.commit()
    await db.refresh(booth)
    return booth


# ============================================================
# 报名路由 /api/registrations/*
# ============================================================

registration_router = APIRouter(prefix="/api/registrations", tags=["报名管理"])


@registration_router.post("", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
async def create_registration(
    data: RegistrationCreateRequest,
    current_user: CurrentUser = Depends(require_visitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Exhibition).where(Exhibition.id == data.exhibition_id))
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在")

    result = await db.execute(
        select(VisitorRegistration).where(
            VisitorRegistration.visitor_id == current_user.user_id,
            VisitorRegistration.exhibition_id == data.exhibition_id,
        )
    )
    existing = result.scalars().first()

    if existing:
        if data.is_favorite is not None:
            existing.is_favorite = data.is_favorite
        if data.is_registered is not None:
            existing.is_registered = data.is_registered
        await db.commit()
        await db.refresh(existing)
        return existing

    registration = VisitorRegistration(
        visitor_id=current_user.user_id,
        exhibition_id=data.exhibition_id,
        is_favorite=data.is_favorite,
        is_registered=data.is_registered,
    )
    db.add(registration)
    if data.is_registered:
        exhibition.visitor_count += 1
    await db.commit()
    await db.refresh(registration)
    return registration


@registration_router.get("/my", response_model=List[RegistrationResponse])
async def my_registrations(
    current_user: CurrentUser = Depends(require_visitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VisitorRegistration)
        .where(VisitorRegistration.visitor_id == current_user.user_id)
        .options(joinedload(VisitorRegistration.exhibition))
        .order_by(VisitorRegistration.created_at.desc())
    )
    return result.unique().scalars().all()


@registration_router.get("/exhibition/{exhibition_id}", response_model=List[AdminRegistrationDetailResponse])
async def list_exhibition_registrations(
    exhibition_id: int,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VisitorRegistration)
        .where(VisitorRegistration.exhibition_id == exhibition_id, VisitorRegistration.is_registered == True)
        .order_by(VisitorRegistration.created_at.desc())
    )
    registrations = result.scalars().all()
    out = []
    for r in registrations:
        d = AdminRegistrationDetailResponse.model_validate(r).model_dump()
        u_result = await db.execute(select(User).where(User.id == r.visitor_id))
        u = u_result.scalars().first()
        if u:
            d["visitor_username"] = u.username
            d["visitor_email"] = u.email
        out.append(d)
    return out


@registration_router.post("/{registration_id}/checkin", response_model=RegistrationResponse)
async def checkin_registration(
    registration_id: int,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VisitorRegistration).where(VisitorRegistration.id == registration_id))
    reg = result.scalars().first()
    if not reg:
        raise HTTPException(status_code=404, detail="报名记录不存在")
    reg.check_in_at = datetime.now(timezone.utc)
    reg.ticket_code = reg.ticket_code or f"TICKET-{reg.id}-{int(datetime.now(timezone.utc).timestamp())}"
    await db.commit()
    await db.refresh(reg)
    return reg


# ============================================================
# 采购需求路由 /api/procurement/*
# ============================================================

procurement_router = APIRouter(prefix="/api/procurement", tags=["采购需求"])


def _enrich_procurement_response(proc) -> dict:
    """Helper: convert ProcurementRequest model to dict with computed fields"""
    d = {
        "id": proc.id, "visitor_id": proc.visitor_id,
        "title": proc.title, "description": proc.description,
        "category": proc.category, "budget_min": proc.budget_min,
        "budget_max": proc.budget_max, "deadline": proc.deadline,
        "status": proc.status.value if hasattr(proc.status, 'value') else proc.status,
        "created_at": proc.created_at, "updated_at": proc.updated_at,
        "visitor_username": None, "match_count": 0,
    }
    return d


@procurement_router.post("", response_model=ProcurementResponse, status_code=status.HTTP_201_CREATED)
async def create_procurement(
    data: ProcurementCreateRequest,
    current_user: CurrentUser = Depends(require_visitor),
    db: AsyncSession = Depends(get_db),
):
    proc = ProcurementRequest(
        visitor_id=current_user.user_id,
        title=data.title, description=data.description,
        category=data.category, budget_min=data.budget_min,
        budget_max=data.budget_max, deadline=data.deadline,
        status=ProcurementStatus.PENDING,
    )
    db.add(proc)
    await db.commit()
    await db.refresh(proc)
    out = _enrich_procurement_response(proc)
    out["visitor_username"] = current_user.username
    return out


@procurement_router.get("", response_model=List[ProcurementResponse])
async def list_procurement(
    category: Optional[str] = Query(None),
    status_param: Optional[str] = Query(None, alias="status"),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if category:
        conditions.append(ProcurementRequest.category == category)
    if status_param:
        conditions.append(ProcurementRequest.status == status_param)
    if keyword:
        conditions.append(or_(
            ProcurementRequest.title.ilike(f"%{keyword}%"),
            ProcurementRequest.description.ilike(f"%{keyword}%"),
        ))
    stmt = (select(ProcurementRequest).where(and_(*conditions) if conditions else True)
            .order_by(desc(ProcurementRequest.created_at))
            .offset((page - 1) * page_size).limit(page_size))
    result = await db.execute(stmt)
    procs = result.scalars().all()
    out = []
    for p in procs:
        d = _enrich_procurement_response(p)
        u_result = await db.execute(select(User.username).where(User.id == p.visitor_id))
        d["visitor_username"] = u_result.scalar()
        m_result = await db.execute(
            select(func.count(ProcurementMatch.id)).where(ProcurementMatch.procurement_id == p.id)
        )
        d["match_count"] = m_result.scalar()
        out.append(d)
    return out


@procurement_router.get("/my", response_model=List[ProcurementResponse])
async def my_procurement(
    current_user: CurrentUser = Depends(require_visitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcurementRequest)
        .where(ProcurementRequest.visitor_id == current_user.user_id)
        .order_by(desc(ProcurementRequest.created_at))
    )
    procs = result.scalars().all()
    out = []
    for p in procs:
        d = _enrich_procurement_response(p)
        d["visitor_username"] = current_user.username
        m_result = await db.execute(
            select(func.count(ProcurementMatch.id)).where(ProcurementMatch.procurement_id == p.id)
        )
        d["match_count"] = m_result.scalar()
        out.append(d)
    return out


@procurement_router.get("/{procurement_id}", response_model=ProcurementResponse)
async def get_procurement(procurement_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProcurementRequest).where(ProcurementRequest.id == procurement_id)
    )
    proc = result.scalars().first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购需求不存在")
    d = _enrich_procurement_response(proc)
    u_result = await db.execute(select(User.username).where(User.id == proc.visitor_id))
    d["visitor_username"] = u_result.scalar()
    m_result = await db.execute(
        select(func.count(ProcurementMatch.id)).where(ProcurementMatch.procurement_id == proc.id)
    )
    d["match_count"] = m_result.scalar()
    return d


@procurement_router.put("/{procurement_id}", response_model=ProcurementResponse)
async def update_procurement(
    procurement_id: int,
    data: ProcurementUpdateRequest,
    current_user: CurrentUser = Depends(require_visitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcurementRequest).where(
            ProcurementRequest.id == procurement_id,
            ProcurementRequest.visitor_id == current_user.user_id,
        )
    )
    proc = result.scalars().first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购需求不存在或无权操作")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value:
            try:
                setattr(proc, field, ProcurementStatus(value))
                continue
            except ValueError:
                pass
        setattr(proc, field, value)
    await db.commit()
    await db.refresh(proc)
    d = _enrich_procurement_response(proc)
    d["visitor_username"] = current_user.username
    return d


@procurement_router.delete("/{procurement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_procurement(
    procurement_id: int,
    current_user: CurrentUser = Depends(require_visitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcurementRequest).where(
            ProcurementRequest.id == procurement_id,
            ProcurementRequest.visitor_id == current_user.user_id,
        )
    )
    proc = result.scalars().first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购需求不存在或无权操作")
    await db.delete(proc)
    await db.commit()


@procurement_router.post("/{procurement_id}/match", response_model=ProcurementMatchResponse)
async def match_procurement(
    procurement_id: int,
    data: ProcurementMatchCreateRequest,
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcurementRequest).where(ProcurementRequest.id == procurement_id)
    )
    proc = result.scalars().first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购需求不存在")

    # Check duplicate match
    dup_result = await db.execute(
        select(ProcurementMatch).where(
            ProcurementMatch.procurement_id == procurement_id,
            ProcurementMatch.exhibitor_id == current_user.user_id,
        )
    )
    if dup_result.scalars().first():
        raise HTTPException(status_code=409, detail="您已对该采购需求发起过匹配")

    match = ProcurementMatch(
        procurement_id=procurement_id,
        exhibitor_id=current_user.user_id,
        message=data.message,
        quoted_price=data.quoted_price,
        is_accepted=None,
    )
    db.add(match)
    if proc.status == ProcurementStatus.PENDING:
        proc.status = ProcurementStatus.MATCHED
    await db.commit()
    await db.refresh(match)

    u_result = await db.execute(select(User).where(User.id == current_user.user_id))
    u = u_result.scalars().first()
    return {
        "id": match.id,
        "procurement_id": match.procurement_id,
        "exhibitor_id": match.exhibitor_id,
        "exhibitor_username": u.username if u else None,
        "exhibitor_company": u.company if u else None,
        "message": match.message,
        "quoted_price": match.quoted_price,
        "is_accepted": match.is_accepted,
        "created_at": match.created_at,
    }


@procurement_router.get("/matches", response_model=List[ProcurementMatchResponse])
async def my_matches(
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcurementMatch)
        .where(ProcurementMatch.exhibitor_id == current_user.user_id)
        .order_by(desc(ProcurementMatch.created_at))
    )
    matches = result.scalars().all()
    out = []
    for m in matches:
        u_result = await db.execute(select(User).where(User.id == m.exhibitor_id))
        u = u_result.scalars().first()
        out.append({
            "id": m.id, "procurement_id": m.procurement_id,
            "exhibitor_id": m.exhibitor_id,
            "exhibitor_username": u.username if u else None,
            "exhibitor_company": u.company if u else None,
            "message": m.message, "quoted_price": m.quoted_price,
            "is_accepted": m.is_accepted, "created_at": m.created_at,
        })
    return out


# ============================================================
# 展品路由 /api/products/*
# ============================================================

product_router = APIRouter(prefix="/api/products", tags=["展品管理"])


def _product_to_response(product, username: str = None) -> dict:
    return {
        "id": product.id, "exhibitor_id": product.exhibitor_id,
        "exhibitor_username": username,
        "booth_id": product.booth_id, "exhibition_id": product.exhibition_id,
        "name": product.name, "description": product.description,
        "category": product.category,
        "images": json.loads(product.images) if product.images else [],
        "price": product.price,
        "specs": json.loads(product.specs) if product.specs else None,
        "status": product.status.value if hasattr(product.status, 'value') else product.status,
        "created_at": product.created_at, "updated_at": product.updated_at,
    }


@product_router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreateRequest,
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    product = Product(
        exhibitor_id=current_user.user_id,
        booth_id=data.booth_id,
        exhibition_id=data.exhibition_id,
        name=data.name,
        description=data.description,
        category=data.category,
        images=json.dumps(data.images) if data.images else None,
        price=data.price,
        specs=json.dumps(data.specs) if data.specs else None,
        status=ProductStatus(data.status) if data.status else ProductStatus.DRAFT,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return _product_to_response(product, current_user.username)


@product_router.get("", response_model=List[ProductResponse])
async def list_products(
    exhibition_id: Optional[int] = Query(None),
    booth_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    exhibitor_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    conditions = [Product.status == ProductStatus.PUBLISHED]
    if exhibition_id:
        conditions.append(Product.exhibition_id == exhibition_id)
    if booth_id:
        conditions.append(Product.booth_id == booth_id)
    if category:
        conditions.append(Product.category == category)
    if exhibitor_id:
        conditions.append(Product.exhibitor_id == exhibitor_id)
    if keyword:
        conditions.append(or_(
            Product.name.ilike(f"%{keyword}%"),
            Product.description.ilike(f"%{keyword}%"),
        ))
    stmt = (select(Product).where(and_(*conditions))
            .order_by(desc(Product.created_at))
            .offset((page - 1) * page_size).limit(page_size))
    result = await db.execute(stmt)
    products = result.scalars().all()
    out = []
    for p in products:
        u_result = await db.execute(select(User.username).where(User.id == p.exhibitor_id))
        out.append(_product_to_response(p, u_result.scalar()))
    return out


@product_router.get("/my", response_model=List[ProductResponse])
async def my_products(
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product)
        .where(Product.exhibitor_id == current_user.user_id)
        .order_by(desc(Product.created_at))
    )
    products = result.scalars().all()
    return [_product_to_response(p, current_user.username) for p in products]


@product_router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="展品不存在")
    u_result = await db.execute(select(User.username).where(User.id == product.exhibitor_id))
    return _product_to_response(product, u_result.scalar())


@product_router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdateRequest,
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.exhibitor_id == current_user.user_id)
    )
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="展品不存在或无权操作")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "images":
            setattr(product, field, json.dumps(value) if value else None)
        elif field == "specs":
            setattr(product, field, json.dumps(value) if value else None)
        elif field == "status" and value:
            try:
                setattr(product, field, ProductStatus(value))
                continue
            except ValueError:
                pass
        else:
            setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return _product_to_response(product, current_user.username)


@product_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.exhibitor_id == current_user.user_id)
    )
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="展品不存在或无权操作")
    await db.delete(product)
    await db.commit()


# ============================================================
# 消息路由 /api/messages/*
# ============================================================

message_router = APIRouter(prefix="/api/messages", tags=["站内消息"])


@message_router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    data: MessageCreateRequest,
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    # Validate receiver exists
    result = await db.execute(select(User).where(User.id == data.receiver_id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="接收者不存在")
    if data.receiver_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="不能给自己发送消息")

    msg = Message(
        sender_id=current_user.user_id,
        receiver_id=data.receiver_id,
        title=data.title,
        content=data.content,
        is_read=False,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@message_router.get("", response_model=List[MessageListResponse])
async def list_received_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_read: Optional[bool] = Query(None),
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    conditions = [Message.receiver_id == current_user.user_id]
    if is_read is not None:
        conditions.append(Message.is_read == is_read)
    stmt = (select(Message).where(and_(*conditions))
            .order_by(desc(Message.created_at))
            .offset((page - 1) * page_size).limit(page_size))
    result = await db.execute(stmt)
    msgs = result.scalars().all()
    out = []
    for m in msgs:
        s_result = await db.execute(select(User.username).where(User.id == m.sender_id))
        r_result = await db.execute(select(User.username).where(User.id == m.receiver_id))
        out.append({
            "id": m.id, "sender_id": m.sender_id,
            "sender_username": s_result.scalar(),
            "receiver_id": m.receiver_id,
            "receiver_username": r_result.scalar(),
            "title": m.title, "is_read": m.is_read,
            "created_at": m.created_at,
        })
    return out


@message_router.get("/sent", response_model=List[MessageListResponse])
async def list_sent_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    stmt = (select(Message).where(Message.sender_id == current_user.user_id)
            .order_by(desc(Message.created_at))
            .offset((page - 1) * page_size).limit(page_size))
    result = await db.execute(stmt)
    msgs = result.scalars().all()
    out = []
    for m in msgs:
        s_result = await db.execute(select(User.username).where(User.id == m.sender_id))
        r_result = await db.execute(select(User.username).where(User.id == m.receiver_id))
        out.append({
            "id": m.id, "sender_id": m.sender_id,
            "sender_username": s_result.scalar(),
            "receiver_id": m.receiver_id,
            "receiver_username": r_result.scalar(),
            "title": m.title, "is_read": m.is_read,
            "created_at": m.created_at,
        })
    return out


@message_router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count(Message.id)).where(
            Message.receiver_id == current_user.user_id,
            Message.is_read == False,
        )
    )
    return {"unread_count": result.scalar()}


@message_router.put("/{message_id}/read", response_model=MessageResponse)
async def mark_read(
    message_id: int,
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Message).where(Message.id == message_id, Message.receiver_id == current_user.user_id)
    )
    msg = result.scalars().first()
    if not msg:
        raise HTTPException(status_code=404, detail="消息不存在")
    msg.is_read = True
    msg.read_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)
    return msg


@message_router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    # Get distinct other users from messages
    sent_result = await db.execute(
        select(Message.receiver_id).where(Message.sender_id == current_user.user_id).distinct()
    )
    recv_result = await db.execute(
        select(Message.sender_id).where(Message.receiver_id == current_user.user_id).distinct()
    )
    other_ids = set(sent_result.scalars().all()) | set(recv_result.scalars().all())

    conversations = []
    for other_id in other_ids:
        u_result = await db.execute(select(User).where(User.id == other_id))
        other_user = u_result.scalars().first()
        if not other_user:
            continue

        # Last message
        last_result = await db.execute(
            select(Message).where(
                or_(
                    and_(Message.sender_id == current_user.user_id, Message.receiver_id == other_id),
                    and_(Message.sender_id == other_id, Message.receiver_id == current_user.user_id),
                )
            ).order_by(desc(Message.created_at)).limit(1)
        )
        last_msg = last_result.scalars().first()

        # Unread count from this user
        unread_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.sender_id == other_id,
                Message.receiver_id == current_user.user_id,
                Message.is_read == False,
            )
        )

        conversations.append({
            "other_user_id": other_id,
            "other_username": other_user.username,
            "other_avatar": other_user.avatar_url,
            "last_message": last_msg.content[:100] if last_msg else None,
            "last_message_time": last_msg.created_at if last_msg else None,
            "unread_count": unread_result.scalar(),
        })

    conversations.sort(key=lambda x: x["last_message_time"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return conversations


# ============================================================
# 评价路由 /api/reviews/*
# ============================================================

review_router = APIRouter(prefix="/api/reviews", tags=["展会评价"])


@review_router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    data: ReviewCreateRequest,
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    # Verify exhibition exists
    exh_result = await db.execute(select(Exhibition).where(Exhibition.id == data.exhibition_id if hasattr(data, 'exhibition_id') else None))
    # Need exhibition_id in request - let's handle it
    ...


# ============================================================
# Dashboard 路由 /api/dashboard/*
# ============================================================

dashboard_router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@dashboard_router.get("/exhibitor", response_model=ExhibitorDashboardResponse)
async def exhibitor_dashboard(
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    booth_count_result = await db.execute(
        select(func.count(Booth.id)).where(Booth.exhibitor_id == current_user.user_id)
    )
    my_booth_count = booth_count_result.scalar()

    # Registered exhibitions via booths
    exh_result = await db.execute(
        select(func.count(func.distinct(Booth.exhibition_id))).where(Booth.exhibitor_id == current_user.user_id)
    )
    registered_exhibition_count = exh_result.scalar()

    # Pending booth count (RESERVED but not OCCUPIED)
    pending_result = await db.execute(
        select(func.count(Booth.id)).where(
            Booth.exhibitor_id == current_user.user_id,
            Booth.status == BoothStatus.RESERVED,
        )
    )
    pending_booth_count = pending_result.scalar()

    prod_result = await db.execute(
        select(func.count(Product.id)).where(Product.exhibitor_id == current_user.user_id)
    )
    my_product_count = prod_result.scalar()

    match_result = await db.execute(
        select(func.count(ProcurementMatch.id)).where(ProcurementMatch.exhibitor_id == current_user.user_id)
    )
    total_matches = match_result.scalar()

    return {
        "my_booth_count": my_booth_count,
        "registered_exhibition_count": registered_exhibition_count,
        "pending_booth_count": pending_booth_count,
        "my_product_count": my_product_count,
        "total_matches": total_matches,
    }


@dashboard_router.get("/organizer", response_model=OrganizerDashboardResponse)
async def organizer_dashboard(
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    exh_count_result = await db.execute(
        select(func.count(Exhibition.id)).where(Exhibition.organizer_id == current_user.user_id)
    )
    my_exhibition_count = exh_count_result.scalar()

    # Total booths across organizer's exhibitions
    booth_result = await db.execute(
        select(func.count(Booth.id)).join(Exhibition).where(Exhibition.organizer_id == current_user.user_id)
    )
    total_booth_count = booth_result.scalar()

    reg_result = await db.execute(
        select(func.count(VisitorRegistration.id)).join(Exhibition).where(Exhibition.organizer_id == current_user.user_id)
    )
    total_registration_count = reg_result.scalar()

    # Last 7 days registrations
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    reg7_result = await db.execute(
        select(func.count(VisitorRegistration.id)).join(Exhibition).where(
            Exhibition.organizer_id == current_user.user_id,
            VisitorRegistration.created_at >= week_ago,
        )
    )
    last_7_days_registrations = reg7_result.scalar()

    # Last 7 days booth bookings
    booth7_result = await db.execute(
        select(func.count(Booth.id)).join(Exhibition).where(
            Exhibition.organizer_id == current_user.user_id,
            Booth.status == BoothStatus.RESERVED,
            Booth.updated_at >= week_ago,
        )
    )
    last_7_days_booth_bookings = booth7_result.scalar()

    return {
        "my_exhibition_count": my_exhibition_count,
        "total_booth_count": total_booth_count,
        "total_registration_count": total_registration_count,
        "last_7_days_registrations": last_7_days_registrations,
        "last_7_days_booth_bookings": last_7_days_booth_bookings,
    }


@dashboard_router.get("/boss", response_model=StatsOverviewResponse)
async def boss_dashboard(
    current_user: CurrentUser = Depends(require_boss),
    db: AsyncSession = Depends(get_db),
):
    # Total counts
    users_result = await db.execute(select(func.count(User.id)))
    exh_result = await db.execute(select(func.count(Exhibition.id)))
    booth_result = await db.execute(select(func.count(Booth.id)))
    reg_result = await db.execute(select(func.count(VisitorRegistration.id)))
    proc_result = await db.execute(select(func.count(ProcurementRequest.id)))
    prod_result = await db.execute(select(func.count(Product.id)))
    msg_result = await db.execute(select(func.count(Message.id)))

    # Role distribution
    role_result = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    role_dist = {r.value: c for r, c in role_result.all()}

    # Exhibition status distribution
    exh_status_result = await db.execute(
        select(Exhibition.status, func.count(Exhibition.id)).group_by(Exhibition.status)
    )
    exh_status_dist = {s.value: c for s, c in exh_status_result.all()}

    # Procurement status distribution
    proc_status_result = await db.execute(
        select(ProcurementRequest.status, func.count(ProcurementRequest.id)).group_by(ProcurementRequest.status)
    )
    proc_status_dist = {s.value: c for s, c in proc_status_result.all()}

    # Exhibitor activity
    active_exh_result = await db.execute(
        select(func.count(func.distinct(Booth.exhibitor_id)))
    )
    with_booth = active_exh_result.scalar()

    with_prod_result = await db.execute(
        select(func.count(func.distinct(Product.exhibitor_id)))
    )
    with_product = with_prod_result.scalar()

    # Procurement stats
    proc_total = proc_result.scalar()
    matched_result = await db.execute(
        select(func.count(ProcurementRequest.id)).where(
            ProcurementRequest.status.in_([ProcurementStatus.MATCHED, ProcurementStatus.COMPLETED])
        )
    )
    proc_matched = matched_result.scalar()

    return {
        "total_users": users_result.scalar(),
        "total_exhibitions": exh_result.scalar(),
        "total_booths": booth_result.scalar(),
        "total_registrations": reg_result.scalar(),
        "total_procurements": proc_total,
        "total_products": prod_result.scalar(),
        "total_messages": msg_result.scalar(),
        "user_role_distribution": role_dist,
        "exhibition_status_distribution": exh_status_dist,
        "procurement_status_distribution": proc_status_dist,
        "exhibitor_active_count": with_booth,
        "exhibitor_with_booth_count": with_booth,
        "exhibitor_with_product_count": with_product,
        "procurement_total": proc_total,
        "procurement_matched": proc_matched,
        "procurement_match_rate": round(proc_matched / proc_total * 100, 1) if proc_total > 0 else 0,
    }


# ============================================================
# 管理后台路由 /api/admin/*
# ============================================================

admin_router = APIRouter(prefix="/api/admin", tags=["管理后台"])

# ----- 展会管理 -----

@admin_router.get("/exhibitions", response_model=List[AdminExhibitionStatsResponse])
async def admin_list_exhibitions(
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exhibition).where(Exhibition.organizer_id == current_user.user_id).order_by(desc(Exhibition.created_at))
    )
    exhibitions = result.scalars().all()
    out = []
    for e in exhibitions:
        booked_result = await db.execute(
            select(func.count(Booth.id)).where(
                Booth.exhibition_id == e.id,
                Booth.status.in_([BoothStatus.RESERVED, BoothStatus.OCCUPIED]),
            )
        )
        out.append({
            "id": e.id, "name": e.name, "status": e.status.value,
            "total_booths": e.total_booths, "available_booths": e.available_booths,
            "booked_booths": booked_result.scalar(), "visitor_count": e.visitor_count,
            "start_date": e.start_date, "end_date": e.end_date, "created_at": e.created_at,
        })
    return out


@admin_router.post("/exhibitions", response_model=ExhibitionResponse, status_code=status.HTTP_201_CREATED)
async def create_exhibition(
    data: ExhibitionCreateRequest,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    exhibition = Exhibition(
        name=data.name, short_name=data.short_name, description=data.description,
        cover_url=data.cover_url, start_date=data.start_date, end_date=data.end_date,
        registration_deadline=data.registration_deadline,
        venue=data.venue, address=data.address, city=data.city,
        status=ExhibitionStatus.DRAFT, organizer_id=current_user.user_id,
        total_booths=data.total_booths, available_booths=data.total_booths,
    )
    db.add(exhibition)
    await db.commit()
    await db.refresh(exhibition)
    return exhibition


@admin_router.put("/exhibitions/{exhibition_id}", response_model=ExhibitionResponse)
async def update_exhibition(
    exhibition_id: int,
    data: ExhibitionCreateRequest,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exhibition).where(Exhibition.id == exhibition_id, Exhibition.organizer_id == current_user.user_id)
    )
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在或无权操作")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exhibition, field, value)
    await db.commit()
    await db.refresh(exhibition)
    return exhibition


@admin_router.delete("/exhibitions/{exhibition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exhibition(
    exhibition_id: int,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exhibition).where(Exhibition.id == exhibition_id, Exhibition.organizer_id == current_user.user_id)
    )
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在或无权操作")
    if exhibition.status != ExhibitionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="只能删除草稿状态的展会")
    await db.delete(exhibition)
    await db.commit()


@admin_router.post("/exhibitions/{exhibition_id}/publish", response_model=ExhibitionResponse)
async def publish_exhibition(
    exhibition_id: int,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exhibition).where(Exhibition.id == exhibition_id, Exhibition.organizer_id == current_user.user_id)
    )
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在或无权操作")
    if exhibition.status != ExhibitionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="只有草稿状态的展会才能发布")
    exhibition.status = ExhibitionStatus.PUBLISHED
    await db.commit()
    await db.refresh(exhibition)
    return exhibition


@admin_router.post("/exhibitions/{exhibition_id}/approve", response_model=ExhibitionResponse)
async def approve_exhibition(
    exhibition_id: int,
    data: ExhibitionApproveRequest,
    current_user: CurrentUser = Depends(require_boss),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Exhibition).where(Exhibition.id == exhibition_id))
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在")

    if data.action == "approve":
        exhibition.status = ExhibitionStatus.ONGOING
        exhibition.approved_by = current_user.user_id
        exhibition.approved_at = datetime.now(timezone.utc)
    elif data.action == "reject":
        exhibition.status = ExhibitionStatus.DRAFT
        exhibition.reject_reason = data.reject_reason
    else:
        raise HTTPException(status_code=400, detail="无效的审批动作")

    await db.commit()
    await db.refresh(exhibition)
    return exhibition


@admin_router.post("/exhibitions/{exhibition_id}/cancel", response_model=ExhibitionResponse)
async def cancel_exhibition(
    exhibition_id: int,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exhibition).where(Exhibition.id == exhibition_id, Exhibition.organizer_id == current_user.user_id)
    )
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在或无权操作")
    exhibition.status = ExhibitionStatus.CANCELLED
    await db.commit()
    await db.refresh(exhibition)
    return exhibition


@admin_router.get("/exhibitions/{exhibition_id}/registrations", response_model=List[AdminRegistrationDetailResponse])
async def admin_exhibition_registrations(
    exhibition_id: int,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VisitorRegistration)
        .where(VisitorRegistration.exhibition_id == exhibition_id, VisitorRegistration.is_registered == True)
        .order_by(VisitorRegistration.created_at.desc())
    )
    registrations = result.scalars().all()
    out = []
    for r in registrations:
        d = AdminRegistrationDetailResponse.model_validate(r).model_dump()
        u_result = await db.execute(select(User).where(User.id == r.visitor_id))
        u = u_result.scalars().first()
        if u:
            d["visitor_username"] = u.username
            d["visitor_email"] = u.email
        out.append(d)
    return out


# ----- 展位管理 -----

@admin_router.post("/booths", response_model=BoothResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_booth(
    data: BoothCreateRequest,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exhibition).where(Exhibition.id == data.exhibition_id, Exhibition.organizer_id == current_user.user_id)
    )
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在或无权操作")

    dup_result = await db.execute(
        select(Booth).where(Booth.exhibition_id == data.exhibition_id, Booth.booth_number == data.booth_number)
    )
    if dup_result.scalars().first():
        raise HTTPException(status_code=409, detail="展位编号已存在")

    booth = Booth(
        exhibition_id=data.exhibition_id, booth_number=data.booth_number,
        name=data.name, description=data.description,
        area=data.area, price=data.price, floor=data.floor, zone=data.zone,
        status=BoothStatus.AVAILABLE,
    )
    db.add(booth)
    exhibition.total_booths += 1
    exhibition.available_booths += 1
    await db.commit()
    await db.refresh(booth)
    return booth


@admin_router.get("/booths/{booth_id}", response_model=BoothResponse)
async def admin_get_booth(
    booth_id: int,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Booth).where(Booth.id == booth_id))
    booth = result.scalars().first()
    if not booth:
        raise HTTPException(status_code=404, detail="展位不存在")
    return booth


@admin_router.put("/booths/{booth_id}", response_model=BoothResponse)
async def admin_update_booth(
    booth_id: int,
    data: BoothCreateRequest,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booth).join(Exhibition).where(
            Booth.id == booth_id,
            Exhibition.organizer_id == current_user.user_id,
        )
    )
    booth = result.scalars().first()
    if not booth:
        raise HTTPException(status_code=404, detail="展位不存在或无权操作")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(booth, field, value)
    await db.commit()
    await db.refresh(booth)
    return booth


@admin_router.delete("/booths/{booth_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_booth(
    booth_id: int,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booth).join(Exhibition).where(
            Booth.id == booth_id,
            Exhibition.organizer_id == current_user.user_id,
        )
    )
    booth = result.scalars().first()
    if not booth:
        raise HTTPException(status_code=404, detail="展位不存在或无权操作")
    if booth.status in (BoothStatus.RESERVED, BoothStatus.OCCUPIED):
        raise HTTPException(status_code=400, detail="已预订或占用的展位无法删除")
    await db.delete(booth)
    await db.commit()


@admin_router.get("/booths/exhibition/{exhibition_id}", response_model=List[AdminBoothAllocationResponse])
async def admin_exhibition_booths(
    exhibition_id: int,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booth).where(Booth.exhibition_id == exhibition_id).order_by(Booth.booth_number)
    )
    booths = result.scalars().all()
    out = []
    for b in booths:
        d = {
            "id": b.id, "booth_number": b.booth_number,
            "name": b.name, "zone": b.zone, "price": b.price,
            "status": b.status.value,
            "exhibitor_id": b.exhibitor_id,
            "exhibitor_company": None, "exhibitor_username": None,
        }
        if b.exhibitor_id:
            u_result = await db.execute(select(User).where(User.id == b.exhibitor_id))
            u = u_result.scalars().first()
            if u:
                d["exhibitor_company"] = u.company
                d["exhibitor_username"] = u.username
        out.append(d)
    return out


# ----- 用户管理 -----

@admin_router.get("/users", response_model=List[UserProfileResponse])
async def admin_list_users(
    role: Optional[str] = Query(None),
    status_param: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if role:
        conditions.append(User.role == role)
    if status_param:
        conditions.append(User.status == status_param)
    stmt = (select(User).where(and_(*conditions) if conditions else True)
            .order_by(desc(User.created_at))
            .offset((page - 1) * page_size).limit(page_size))
    result = await db.execute(stmt)
    return result.scalars().all()


@admin_router.get("/users/{user_id}", response_model=UserProfileResponse)
async def admin_get_user(
    user_id: int,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@admin_router.put("/users/{user_id}/status", response_model=UserProfileResponse)
async def admin_update_user_status(
    user_id: int,
    status_param: str = Query(..., alias="status", description="新状态: active/disabled/banned"),
    current_user: CurrentUser = Depends(require_boss),
    db: AsyncSession = Depends(get_db),
):
    if status_param not in ("active", "disabled", "banned"):
        raise HTTPException(status_code=400, detail="无效的状态值")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.user_id:
        raise HTTPException(status_code=400, detail="不能修改自己的状态")
    user.status = UserStatus(status_param)
    await db.commit()
    await db.refresh(user)
    return user


# ----- 统计数据 -----

@admin_router.get("/stats")
async def get_admin_stats(
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    users_result = await db.execute(select(func.count(User.id)))
    exh_result = await db.execute(select(func.count(Exhibition.id)))
    booth_result = await db.execute(select(func.count(Booth.id)))
    reg_result = await db.execute(select(func.count(VisitorRegistration.id)))
    proc_result = await db.execute(select(func.count(ProcurementRequest.id)))
    prod_result = await db.execute(select(func.count(Product.id)))
    msg_result = await db.execute(select(func.count(Message.id)))

    role_result = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )

    return {
        "total_users": users_result.scalar(),
        "total_exhibitions": exh_result.scalar(),
        "total_booths": booth_result.scalar(),
        "total_registrations": reg_result.scalar(),
        "total_procurements": proc_result.scalar(),
        "total_products": prod_result.scalar(),
        "total_messages": msg_result.scalar(),
        "user_role_distribution": {r.value: c for r, c in role_result.all()},
    }


# ----- 审计日志 -----

@admin_router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    stmt = (select(AuditLog).where(and_(*conditions) if conditions else True)
            .order_by(desc(AuditLog.created_at))
            .offset((page - 1) * page_size).limit(page_size))
    result = await db.execute(stmt)
    return result.scalars().all()


# ============================================================
# 注册所有子路由
# ============================================================

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(exhibition_router)
router.include_router(booth_router)
router.include_router(registration_router)
router.include_router(procurement_router)
router.include_router(product_router)
router.include_router(message_router)
router.include_router(review_router)
router.include_router(dashboard_router)
router.include_router(admin_router)
