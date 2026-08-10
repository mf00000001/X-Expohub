"""
ExpoHub API 路由

路由分层设计：
- /api/auth/*        — 认证相关（登录、注册、刷新令牌）
- /api/users/*       — 用户管理（个人信息）
- /api/exhibitions/* — 展会管理（含市场推荐）
- /api/booths/*      — 展位管理
- /api/registrations/* — 报名管理（游客收藏/报名）
- /api/exhibitor/*   — 展商端（报名展会、个人中心）
- /api/buyer/*       — 买家端（注册展会、我的报名）
- /api/procurement/* — 采购需求
- /api/admin/*       — 管理后台（主办方/老板专用）

五端路由隔离：
- 游客端：/api/exhibitions, /api/registrations
- 买家端：/api/buyer/*, /api/procurement/*
- 展商端：/api/exhibitor/*, /api/booths (预订/管理自己的展位)
- 主办方端：/api/admin/exhibitions, /api/admin/booths, /api/admin/enrollments
- 老板端：/api/admin/stats, /api/admin/approve
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.database import get_db
from src.models import (
    User, UserRole, UserStatus, Exhibition, ExhibitionStatus,
    Booth, BoothStatus, VisitorRegistration, AuditLog,
    ExhibitionEnrollment, EnrollmentStatus,
    ProcurementRequest, ProcurementStatus, ProcurementMatch,
    Product, ProductStatus, Message, Review,
)
from src.schemas import (
    # 认证
    LoginRequest, TokenResponse, RefreshTokenRequest, RefreshTokenResponse,
    # 用户
    RegisterRequest, UserProfileResponse, UserUpdateRequest,
    # 展会
    ExhibitionCreateRequest, ExhibitionResponse, ExhibitionListResponse,
    ExhibitionMarketResponse,
    # 展位
    BoothCreateRequest, BoothResponse, BoothBookRequest,
    # 报名
    RegistrationCreateRequest, RegistrationResponse,
    EnrollmentCreateRequest, EnrollmentResponse, EnrollmentApprovalRequest,
    # 采购
    ProcurementCreateRequest, ProcurementUpdateRequest,
    ProcurementResponse, ProcurementMatchCreateRequest, ProcurementMatchResponse,
    # 展品
    ProductCreateRequest, ProductUpdateRequest, ProductResponse,
    # 展商中心
    ExhibitorCenterResponse, ExhibitorExhibitionGroup,
    # 通用
    ErrorResponse, ApiResponse, PaginatedResponse,
)
from src.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, refresh_access_token,
    get_current_user, require_auth,
    require_role, require_permission, require_visitor, require_buyer,
    require_exhibitor, require_organizer, require_boss, require_staff,
    require_visitor_or_buyer,
    CurrentUser, Permission, UserRole as AuthRole,
)

# ============================================================
# 主路由
# ============================================================

router = APIRouter()


# ============================================================
# 健康检查
# ============================================================

@router.get("/health", tags=["health"])
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "service": "ExpoHub API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# 认证路由 - /api/auth/*
# ============================================================

auth_router = APIRouter(prefix="/api/auth", tags=["认证"])


@auth_router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户注册 — 支持 visitor/buyer/exhibitor/organizer/boss 五类角色"""
    result = await db.execute(
        select(User).where(
            or_(User.username == data.username, User.email == data.email)
        )
    )
    existing = result.scalars().first()
    if existing:
        if existing.username == data.username:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已被注册")

    user = User(
        username=data.username,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=data.role,
        status=UserStatus.ACTIVE,
        nickname=data.nickname or data.username,
        company=data.company,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user_id=user.id, role=user.role.value)
    refresh_token = create_refresh_token(user_id=user.id, role=user.role.value)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=15 * 60,
        user=UserProfileResponse.model_validate(user),
    )


@auth_router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户登录 — 支持用户名或邮箱"""
    result = await db.execute(
        select(User).where(
            or_(User.username == data.username, User.email == data.username)
        )
    )
    user = result.scalars().first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名/邮箱或密码错误")

    if user.status == UserStatus.DISABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    if user.status == UserStatus.BANNED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被封禁")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(user_id=user.id, role=user.role.value)
    refresh_token = create_refresh_token(user_id=user.id, role=user.role.value)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=15 * 60,
        user=UserProfileResponse.model_validate(user),
    )


@auth_router.post("/refresh", response_model=RefreshTokenResponse, summary="刷新访问令牌")
async def refresh_token(data: RefreshTokenRequest):
    """使用刷新令牌获取新的访问令牌"""
    result = refresh_access_token(data.refresh_token)
    return RefreshTokenResponse(**result)


@auth_router.get("/me", response_model=UserProfileResponse, summary="获取当前用户信息")
async def get_my_profile(
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    return result.scalars().first()


# ============================================================
# 用户路由 - /api/users/*
# ============================================================

users_router = APIRouter(prefix="/api/users", tags=["用户管理"])


@users_router.get("/me", response_model=UserProfileResponse, summary="获取个人信息")
async def get_profile(
    current_user: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.user_id))
    return result.scalars().first()


@users_router.put("/me", response_model=UserProfileResponse, summary="更新个人信息")
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
# 展会路由 - /api/exhibitions/*
# ============================================================

exhibition_router = APIRouter(prefix="/api/exhibitions", tags=["展会管理"])


@exhibition_router.get(
    "/market",
    response_model=List[ExhibitionMarketResponse],
    summary="推荐展会市场（首页）",
    description="返回推荐展会市场列表，按热门程度/报名人数排序，供首页展示",
)
async def exhibition_market(
    city: Optional[str] = Query(None, description="按城市筛选"),
    keyword: Optional[str] = Query(None, description="按关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """
    推荐展会市场 — 首页专用接口

    返回进行中和即将开始的展会，附带展商数、买家数、采购需求数等市场数据。
    按 visitor_count 降序排列（最热展会优先）。
    """
    conditions = [
        Exhibition.status.in_([
            ExhibitionStatus.PUBLISHED,
            ExhibitionStatus.ONGOING,
        ])
    ]
    if city:
        conditions.append(Exhibition.city == city)
    if keyword:
        conditions.append(
            or_(
                Exhibition.name.ilike(f"%{keyword}%"),
                Exhibition.description.ilike(f"%{keyword}%"),
                Exhibition.venue.ilike(f"%{keyword}%"),
            )
        )

    stmt = (
        select(Exhibition)
        .where(and_(*conditions))
        .order_by(Exhibition.visitor_count.desc(), Exhibition.start_date.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    exhibitions = result.scalars().all()

    market_list = []
    for exh in exhibitions:
        # 统计已报名展商数
        exhibitor_count_result = await db.execute(
            select(func.count(ExhibitionEnrollment.id)).where(
                ExhibitionEnrollment.exhibition_id == exh.id,
                ExhibitionEnrollment.enrollment_type == "exhibitor",
                ExhibitionEnrollment.status == EnrollmentStatus.APPROVED,
            )
        )
        exhibitor_count = exhibitor_count_result.scalar() or 0

        # 统计已注册买家数
        buyer_count_result = await db.execute(
            select(func.count(ExhibitionEnrollment.id)).where(
                ExhibitionEnrollment.exhibition_id == exh.id,
                ExhibitionEnrollment.enrollment_type == "buyer",
                ExhibitionEnrollment.status == EnrollmentStatus.APPROVED,
            )
        )
        buyer_count = buyer_count_result.scalar() or 0

        # 统计采购需求数
        procurement_count_result = await db.execute(
            select(func.count(ProcurementRequest.id)).where(
                ProcurementRequest.exhibition_id == exh.id,
            )
        )
        procurement_count = procurement_count_result.scalar() or 0

        # 热门品类（取该展会出现最多的采购品类）
        hot_cat_result = await db.execute(
            select(ProcurementRequest.category, func.count(ProcurementRequest.id))
            .where(ProcurementRequest.exhibition_id == exh.id)
            .group_by(ProcurementRequest.category)
            .order_by(func.count(ProcurementRequest.id).desc())
            .limit(1)
        )
        hot_cat_row = hot_cat_result.first()
        hot_category = hot_cat_row[0] if hot_cat_row else None

        # 是否推荐：visitor_count > 50 或 展商数 > 10
        is_recommended = exh.visitor_count > 50 or exhibitor_count > 10

        market_list.append(ExhibitionMarketResponse(
            id=exh.id,
            name=exh.name,
            short_name=exh.short_name,
            cover_url=exh.cover_url,
            description=exh.description,
            start_date=exh.start_date,
            end_date=exh.end_date,
            venue=exh.venue,
            city=exh.city,
            status=exh.status.value if hasattr(exh.status, 'value') else exh.status,
            total_booths=exh.total_booths,
            available_booths=exh.available_booths,
            visitor_count=exh.visitor_count,
            exhibitor_count=exhibitor_count,
            buyer_count=buyer_count,
            procurement_count=procurement_count,
            is_recommended=is_recommended,
            hot_category=hot_category,
        ))

    return market_list


@exhibition_router.get(
    "",
    response_model=List[ExhibitionListResponse],
    summary="获取展会列表",
)
async def list_exhibitions(
    city: Optional[str] = Query(None, description="按城市筛选"),
    status_param: Optional[str] = Query(None, alias="status", description="按状态筛选"),
    keyword: Optional[str] = Query(None, description="按关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取展会列表（公开）"""
    conditions = []
    if status_param:
        conditions.append(Exhibition.status == status_param)
    else:
        conditions.append(
            Exhibition.status.in_([ExhibitionStatus.PUBLISHED, ExhibitionStatus.ONGOING])
        )

    if city:
        conditions.append(Exhibition.city == city)
    if keyword:
        conditions.append(
            or_(
                Exhibition.name.ilike(f"%{keyword}%"),
                Exhibition.description.ilike(f"%{keyword}%"),
                Exhibition.venue.ilike(f"%{keyword}%"),
            )
        )

    stmt = select(Exhibition).where(and_(*conditions)) \
        .order_by(Exhibition.start_date.asc()) \
        .offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    return result.scalars().all()


@exhibition_router.get(
    "/{exhibition_id}",
    response_model=ExhibitionResponse,
    summary="获取展会详情",
)
async def get_exhibition(
    exhibition_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Exhibition).where(Exhibition.id == exhibition_id))
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在")
    return exhibition


# ============================================================
# 展商路由 - /api/exhibitor/*
# ============================================================

exhibitor_router = APIRouter(prefix="/api/exhibitor", tags=["展商端"])


@exhibitor_router.post(
    "/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="展商报名展会",
    description="展商报名参加展会，提交后等待主办方审核",
)
async def enroll_exhibition(
    data: EnrollmentCreateRequest,
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    """展商报名展会"""
    # 验证展会存在且可报名
    result = await db.execute(select(Exhibition).where(Exhibition.id == data.exhibition_id))
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在")

    if exhibition.status not in [ExhibitionStatus.PUBLISHED, ExhibitionStatus.ONGOING]:
        raise HTTPException(status_code=400, detail="该展会当前不可报名")

    # 检查是否已报名
    result = await db.execute(
        select(ExhibitionEnrollment).where(
            ExhibitionEnrollment.user_id == current_user.user_id,
            ExhibitionEnrollment.exhibition_id == data.exhibition_id,
            ExhibitionEnrollment.enrollment_type == "exhibitor",
        )
    )
    existing = result.scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="您已报名该展会，请勿重复报名")

    enrollment = ExhibitionEnrollment(
        user_id=current_user.user_id,
        exhibition_id=data.exhibition_id,
        enrollment_type="exhibitor",
        status=EnrollmentStatus.PENDING,
        company_name=data.company_name,
        contact_phone=data.contact_phone,
        remark=data.remark,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)

    # 附带展会信息
    result = await db.execute(
        select(ExhibitionEnrollment)
        .options(joinedload(ExhibitionEnrollment.exhibition))
        .where(ExhibitionEnrollment.id == enrollment.id)
    )
    return result.unique().scalars().first()


@exhibitor_router.get(
    "/enrollments",
    response_model=List[EnrollmentResponse],
    summary="展商我的报名列表",
    description="查看当前展商所有报名记录（按展会自动分组可配合 /center 接口）",
)
async def my_enrollments(
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    """展商查看自己的报名列表"""
    result = await db.execute(
        select(ExhibitionEnrollment)
        .options(joinedload(ExhibitionEnrollment.exhibition))
        .where(
            ExhibitionEnrollment.user_id == current_user.user_id,
            ExhibitionEnrollment.enrollment_type == "exhibitor",
        )
        .order_by(ExhibitionEnrollment.created_at.desc())
    )
    return result.unique().scalars().all()


@exhibitor_router.get(
    "/center",
    response_model=ExhibitorCenterResponse,
    summary="展商个人中心（按展会自动分组）",
    description="展商个人中心：按展会分组展示该展商的所有展位、展品、报名信息、采购匹配",
)
async def exhibitor_center(
    current_user: CurrentUser = Depends(require_exhibitor),
    db: AsyncSession = Depends(get_db),
):
    """展商个人中心 — 按展会自动分组"""
    # 获取该展商所有报名记录（已通过审核的）
    enrollments_result = await db.execute(
        select(ExhibitionEnrollment)
        .options(joinedload(ExhibitionEnrollment.exhibition))
        .where(
            ExhibitionEnrollment.user_id == current_user.user_id,
            ExhibitionEnrollment.enrollment_type == "exhibitor",
        )
        .order_by(ExhibitionEnrollment.created_at.desc())
    )
    enrollments = enrollments_result.unique().scalars().all()

    # 获取该展商所有展位
    booths_result = await db.execute(
        select(Booth)
        .options(joinedload(Booth.exhibition))
        .where(Booth.exhibitor_id == current_user.user_id)
    )
    booths = booths_result.unique().scalars().all()

    # 获取该展商所有展品
    products_result = await db.execute(
        select(Product)
        .options(joinedload(Product.exhibition))
        .where(Product.exhibitor_id == current_user.user_id)
        .order_by(Product.created_at.desc())
    )
    products = products_result.unique().scalars().all()

    # 获取该展商所有采购匹配
    matches_result = await db.execute(
        select(ProcurementMatch)
        .options(
            joinedload(ProcurementMatch.procurement).joinedload(ProcurementRequest.exhibition)
        )
        .where(ProcurementMatch.exhibitor_id == current_user.user_id)
        .order_by(ProcurementMatch.created_at.desc())
    )
    matches = matches_result.unique().scalars().all()

    # 按展会展商报名记录分组
    exhibition_map: dict[int, dict] = {}

    # 先以报名记录建立分组
    for enrollment in enrollments:
        exh = enrollment.exhibition
        if exh and exh.id not in exhibition_map:
            exhibition_map[exh.id] = {
                "exhibition": exh,
                "enrollment": enrollment,
                "booths": [],
                "products": [],
                "procurement_matches": [],
            }

    # 填充展位（可能有没有报名但已预订的展会）
    for booth in booths:
        exh = booth.exhibition
        if exh:
            if exh.id not in exhibition_map:
                exhibition_map[exh.id] = {
                    "exhibition": exh,
                    "enrollment": None,
                    "booths": [],
                    "products": [],
                    "procurement_matches": [],
                }
            exhibition_map[exh.id]["booths"].append(booth)

    # 填充展品
    for prod in products:
        exh = prod.exhibition
        if exh:
            if exh.id not in exhibition_map:
                exhibition_map[exh.id] = {
                    "exhibition": exh,
                    "enrollment": None,
                    "booths": [],
                    "products": [],
                    "procurement_matches": [],
                }
            exhibition_map[exh.id]["products"].append(prod)

    # 填充采购匹配
    for match in matches:
        if match.procurement:
            exh = match.procurement.exhibition
            if exh:
                if exh.id not in exhibition_map:
                    exhibition_map[exh.id] = {
                        "exhibition": exh,
                        "enrollment": None,
                        "booths": [],
                        "products": [],
                        "procurement_matches": [],
                    }
                exhibition_map[exh.id]["procurement_matches"].append(match)

    # 构建响应
    groups = []
    total_booths = 0
    total_products = 0
    total_matches = 0

    for exh_id, data in exhibition_map.items():
        exh = data["exhibition"]
        booth_list = data["booths"]
        product_list = data["products"]
        match_list = data["procurement_matches"]
        enrollment = data["enrollment"]

        total_booths += len(booth_list)
        total_products += len(product_list)
        total_matches += len(match_list)

        groups.append(ExhibitorExhibitionGroup(
            exhibition_id=exh.id,
            exhibition_name=exh.name,
            exhibition_cover=exh.cover_url,
            exhibition_status=exh.status.value if hasattr(exh.status, 'value') else exh.status,
            exhibition_city=exh.city,
            start_date=exh.start_date,
            end_date=exh.end_date,
            booths=[BoothResponse.model_validate(b) for b in booth_list],
            products=[ProductResponse(
                id=p.id, exhibitor_id=p.exhibitor_id,
                booth_id=p.booth_id, exhibition_id=p.exhibition_id,
                name=p.name, description=p.description, category=p.category,
                images=json.loads(p.images) if p.images else None,
                price=p.price, specs=json.loads(p.specs) if p.specs else None,
                status=p.status.value if hasattr(p.status, 'value') else p.status,
                created_at=p.created_at, updated_at=p.updated_at,
            ) for p in product_list],
            enrollment=EnrollmentResponse.model_validate(enrollment) if enrollment else None,
            procurement_matches=[ProcurementMatchResponse(
                id=m.id, procurement_id=m.procurement_id,
                exhibitor_id=m.exhibitor_id,
                message=m.message, quoted_price=m.quoted_price,
                is_accepted=m.is_accepted, created_at=m.created_at,
            ) for m in match_list],
            booth_count=len(booth_list),
            product_count=len(product_list),
            match_count=len(match_list),
        ))

    return ExhibitorCenterResponse(
        total_exhibitions=len(groups),
        total_booths=total_booths,
        total_products=total_products,
        total_matches=total_matches,
        groups=groups,
    )


# ============================================================
# 买家路由 - /api/buyer/*
# ============================================================

buyer_router = APIRouter(prefix="/api/buyer", tags=["买家端"])


@buyer_router.post(
    "/register",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="买家注册展会",
    description="买家注册参加展会，提交后等待主办方审核",
)
async def register_exhibition(
    data: EnrollmentCreateRequest,
    current_user: CurrentUser = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    """买家注册展会"""
    # 验证展会存在且可报名
    result = await db.execute(select(Exhibition).where(Exhibition.id == data.exhibition_id))
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在")

    if exhibition.status not in [ExhibitionStatus.PUBLISHED, ExhibitionStatus.ONGOING]:
        raise HTTPException(status_code=400, detail="该展会当前不可注册")

    # 检查是否已注册
    result = await db.execute(
        select(ExhibitionEnrollment).where(
            ExhibitionEnrollment.user_id == current_user.user_id,
            ExhibitionEnrollment.exhibition_id == data.exhibition_id,
            ExhibitionEnrollment.enrollment_type == "buyer",
        )
    )
    existing = result.scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="您已注册该展会，请勿重复注册")

    enrollment = ExhibitionEnrollment(
        user_id=current_user.user_id,
        exhibition_id=data.exhibition_id,
        enrollment_type="buyer",
        status=EnrollmentStatus.PENDING,
        company_name=data.company_name,
        contact_phone=data.contact_phone,
        remark=data.remark,
    )
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)

    # 附带展会信息
    result = await db.execute(
        select(ExhibitionEnrollment)
        .options(joinedload(ExhibitionEnrollment.exhibition))
        .where(ExhibitionEnrollment.id == enrollment.id)
    )
    return result.unique().scalars().first()


@buyer_router.get(
    "/registrations",
    response_model=List[EnrollmentResponse],
    summary="买家我报名的展会列表",
    description="查看当前买家所有展会注册记录",
)
async def my_registrations(
    current_user: CurrentUser = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    """买家查看自己报名的展会列表"""
    result = await db.execute(
        select(ExhibitionEnrollment)
        .options(joinedload(ExhibitionEnrollment.exhibition))
        .where(
            ExhibitionEnrollment.user_id == current_user.user_id,
            ExhibitionEnrollment.enrollment_type == "buyer",
        )
        .order_by(ExhibitionEnrollment.created_at.desc())
    )
    return result.unique().scalars().all()


# ============================================================
# 采购需求路由 - /api/procurement/*
# ============================================================

procurement_router = APIRouter(prefix="/api/procurement", tags=["采购需求"])


@procurement_router.post(
    "",
    response_model=ProcurementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="发布采购需求（需带 exhibition_id）",
    description="买家/游客发布采购需求，必须关联展会",
)
async def create_procurement(
    data: ProcurementCreateRequest,
    current_user: CurrentUser = Depends(require_visitor_or_buyer),
    db: AsyncSession = Depends(get_db),
):
    """发布采购需求 — exhibition_id 必填"""
    # 验证展会存在
    result = await db.execute(select(Exhibition).where(Exhibition.id == data.exhibition_id))
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在")

    procurement = ProcurementRequest(
        visitor_id=current_user.user_id,
        exhibition_id=data.exhibition_id,
        title=data.title,
        description=data.description,
        category=data.category,
        budget_min=data.budget_min,
        budget_max=data.budget_max,
        deadline=data.deadline,
        status=ProcurementStatus.PENDING,
    )
    db.add(procurement)
    await db.commit()
    await db.refresh(procurement)

    return ProcurementResponse(
        id=procurement.id,
        visitor_id=procurement.visitor_id,
        exhibition_id=procurement.exhibition_id,
        exhibition_name=exhibition.name,
        title=procurement.title,
        description=procurement.description,
        category=procurement.category,
        budget_min=procurement.budget_min,
        budget_max=procurement.budget_max,
        deadline=procurement.deadline,
        status=procurement.status.value if hasattr(procurement.status, 'value') else procurement.status,
        match_count=0,
        created_at=procurement.created_at,
        updated_at=procurement.updated_at,
    )


@procurement_router.get(
    "",
    response_model=List[ProcurementResponse],
    summary="获取采购需求列表",
)
async def list_procurements(
    exhibition_id: Optional[int] = Query(None, description="按展会筛选"),
    category: Optional[str] = Query(None, description="按品类筛选"),
    status_param: Optional[str] = Query(None, alias="status", description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取采购需求列表 — 可按展会、品类、状态筛选"""
    conditions = []
    if exhibition_id:
        conditions.append(ProcurementRequest.exhibition_id == exhibition_id)
    if category:
        conditions.append(ProcurementRequest.category == category)
    if status_param:
        conditions.append(ProcurementRequest.status == status_param)
    else:
        conditions.append(ProcurementRequest.status == ProcurementStatus.PENDING)

    stmt = (
        select(ProcurementRequest)
        .options(joinedload(ProcurementRequest.exhibition))
        .where(and_(*conditions))
        .order_by(ProcurementRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    procurements = result.unique().scalars().all()

    response_list = []
    for p in procurements:
        # 统计匹配数
        match_count_result = await db.execute(
            select(func.count(ProcurementMatch.id)).where(
                ProcurementMatch.procurement_id == p.id
            )
        )
        match_count = match_count_result.scalar() or 0

        response_list.append(ProcurementResponse(
            id=p.id,
            visitor_id=p.visitor_id,
            exhibition_id=p.exhibition_id,
            exhibition_name=p.exhibition.name if p.exhibition else None,
            title=p.title,
            description=p.description,
            category=p.category,
            budget_min=p.budget_min,
            budget_max=p.budget_max,
            deadline=p.deadline,
            status=p.status.value if hasattr(p.status, 'value') else p.status,
            match_count=match_count,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))

    return response_list


@procurement_router.get(
    "/my",
    response_model=List[ProcurementResponse],
    summary="我的采购需求",
)
async def my_procurements(
    current_user: CurrentUser = Depends(require_visitor_or_buyer),
    db: AsyncSession = Depends(get_db),
):
    """查看当前用户发布的采购需求"""
    result = await db.execute(
        select(ProcurementRequest)
        .options(joinedload(ProcurementRequest.exhibition))
        .where(ProcurementRequest.visitor_id == current_user.user_id)
        .order_by(ProcurementRequest.created_at.desc())
    )
    procurements = result.unique().scalars().all()

    response_list = []
    for p in procurements:
        match_count_result = await db.execute(
            select(func.count(ProcurementMatch.id)).where(
                ProcurementMatch.procurement_id == p.id
            )
        )
        match_count = match_count_result.scalar() or 0

        response_list.append(ProcurementResponse(
            id=p.id,
            visitor_id=p.visitor_id,
            exhibition_id=p.exhibition_id,
            exhibition_name=p.exhibition.name if p.exhibition else None,
            title=p.title,
            description=p.description,
            category=p.category,
            budget_min=p.budget_min,
            budget_max=p.budget_max,
            deadline=p.deadline,
            status=p.status.value if hasattr(p.status, 'value') else p.status,
            match_count=match_count,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))

    return response_list


@procurement_router.get(
    "/{procurement_id}",
    response_model=ProcurementResponse,
    summary="获取采购需求详情",
)
async def get_procurement(
    procurement_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcurementRequest)
        .options(joinedload(ProcurementRequest.exhibition))
        .where(ProcurementRequest.id == procurement_id)
    )
    p = result.unique().scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="采购需求不存在")

    match_count_result = await db.execute(
        select(func.count(ProcurementMatch.id)).where(
            ProcurementMatch.procurement_id == p.id
        )
    )
    match_count = match_count_result.scalar() or 0

    return ProcurementResponse(
        id=p.id,
        visitor_id=p.visitor_id,
        exhibition_id=p.exhibition_id,
        exhibition_name=p.exhibition.name if p.exhibition else None,
        title=p.title,
        description=p.description,
        category=p.category,
        budget_min=p.budget_min,
        budget_max=p.budget_max,
        deadline=p.deadline,
        status=p.status.value if hasattr(p.status, 'value') else p.status,
        match_count=match_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@procurement_router.put(
    "/{procurement_id}",
    response_model=ProcurementResponse,
    summary="更新采购需求",
)
async def update_procurement(
    procurement_id: int,
    data: ProcurementUpdateRequest,
    current_user: CurrentUser = Depends(require_visitor_or_buyer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcurementRequest)
        .options(joinedload(ProcurementRequest.exhibition))
        .where(
            ProcurementRequest.id == procurement_id,
            ProcurementRequest.visitor_id == current_user.user_id,
        )
    )
    p = result.unique().scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="采购需求不存在或无权操作")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(p, field, value)

    await db.commit()
    await db.refresh(p)

    match_count_result = await db.execute(
        select(func.count(ProcurementMatch.id)).where(
            ProcurementMatch.procurement_id == p.id
        )
    )
    match_count = match_count_result.scalar() or 0

    return ProcurementResponse(
        id=p.id, visitor_id=p.visitor_id,
        exhibition_id=p.exhibition_id,
        exhibition_name=p.exhibition.name if p.exhibition else None,
        title=p.title, description=p.description, category=p.category,
        budget_min=p.budget_min, budget_max=p.budget_max,
        deadline=p.deadline,
        status=p.status.value if hasattr(p.status, 'value') else p.status,
        match_count=match_count,
        created_at=p.created_at, updated_at=p.updated_at,
    )


@procurement_router.delete(
    "/{procurement_id}",
    summary="删除采购需求",
)
async def delete_procurement(
    procurement_id: int,
    current_user: CurrentUser = Depends(require_visitor_or_buyer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProcurementRequest).where(
            ProcurementRequest.id == procurement_id,
            ProcurementRequest.visitor_id == current_user.user_id,
        )
    )
    p = result.scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="采购需求不存在或无权操作")

    await db.delete(p)
    await db.commit()
    return {"message": "已删除"}


# ============================================================
# 主办方管理路由 - /api/admin/*
# ============================================================

admin_router = APIRouter(prefix="/api/admin", tags=["管理后台"])


@admin_router.post(
    "/exhibitions",
    response_model=ExhibitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建展会（主办方）",
)
async def create_exhibition(
    data: ExhibitionCreateRequest,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    exhibition = Exhibition(
        name=data.name,
        short_name=data.short_name,
        description=data.description,
        cover_url=data.cover_url,
        start_date=data.start_date,
        end_date=data.end_date,
        registration_deadline=data.registration_deadline,
        venue=data.venue,
        address=data.address,
        city=data.city,
        status=ExhibitionStatus.DRAFT,
        organizer_id=current_user.user_id,
        total_booths=data.total_booths,
        available_booths=data.total_booths,
    )
    db.add(exhibition)
    await db.commit()
    await db.refresh(exhibition)
    return exhibition


@admin_router.put(
    "/exhibitions/{exhibition_id}",
    response_model=ExhibitionResponse,
    summary="更新展会信息（主办方）",
)
async def update_exhibition(
    exhibition_id: int,
    data: ExhibitionCreateRequest,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exhibition).where(
            Exhibition.id == exhibition_id,
            Exhibition.organizer_id == current_user.user_id,
        )
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


@admin_router.post(
    "/exhibitions/{exhibition_id}/publish",
    response_model=ExhibitionResponse,
    summary="发布展会（主办方）",
)
async def publish_exhibition(
    exhibition_id: int,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exhibition).where(
            Exhibition.id == exhibition_id,
            Exhibition.organizer_id == current_user.user_id,
        )
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


@admin_router.post(
    "/exhibitions/{exhibition_id}/approve",
    response_model=ExhibitionResponse,
    summary="审批展会（老板）",
)
async def approve_exhibition(
    exhibition_id: int,
    current_user: CurrentUser = Depends(require_boss),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Exhibition).where(Exhibition.id == exhibition_id))
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在")

    if exhibition.status != ExhibitionStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="只有已发布的展会才能审批")

    exhibition.status = ExhibitionStatus.ONGOING
    exhibition.approved_by = current_user.user_id
    exhibition.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(exhibition)
    return exhibition


# ============================================================
# 报名审核 - /api/admin/enrollments/*
# ============================================================

@admin_router.get(
    "/enrollments",
    response_model=List[EnrollmentResponse],
    summary="报名列表（主办方）",
    description="主办方查看展会报名列表（展商报名 + 买家注册）",
)
async def list_enrollments(
    exhibition_id: Optional[int] = Query(None, description="按展会筛选"),
    enrollment_type: Optional[str] = Query(None, description="按类型筛选: exhibitor / buyer"),
    status_param: Optional[str] = Query(None, alias="status", description="按审核状态筛选"),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if exhibition_id:
        conditions.append(ExhibitionEnrollment.exhibition_id == exhibition_id)
    if enrollment_type:
        conditions.append(ExhibitionEnrollment.enrollment_type == enrollment_type)
    if status_param:
        conditions.append(ExhibitionEnrollment.status == status_param)

    result = await db.execute(
        select(ExhibitionEnrollment)
        .options(joinedload(ExhibitionEnrollment.exhibition))
        .where(and_(*conditions) if conditions else True)
        .order_by(ExhibitionEnrollment.created_at.desc())
    )
    return result.unique().scalars().all()


@admin_router.post(
    "/enrollments/{enrollment_id}/approve",
    response_model=EnrollmentResponse,
    summary="审核报名（主办方）",
    description="主办方审核展商报名或买家注册：approve(通过) / reject(驳回)",
)
async def approve_enrollment(
    enrollment_id: int,
    data: EnrollmentApprovalRequest,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExhibitionEnrollment)
        .options(joinedload(ExhibitionEnrollment.exhibition))
        .where(ExhibitionEnrollment.id == enrollment_id)
    )
    enrollment = result.unique().scalars().first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="报名记录不存在")

    if data.action == "approve":
        enrollment.status = EnrollmentStatus.APPROVED
        # 更新展会统计
        result = await db.execute(select(Exhibition).where(Exhibition.id == enrollment.exhibition_id))
        exhibition = result.scalars().first()
        if exhibition:
            exhibition.visitor_count += 1
    elif data.action == "reject":
        enrollment.status = EnrollmentStatus.REJECTED
        enrollment.remark = (enrollment.remark or "") + f"\n[驳回原因] {data.reject_reason}"
    else:
        raise HTTPException(status_code=400, detail="无效的审批动作，请使用 approve 或 reject")

    await db.commit()
    await db.refresh(enrollment)
    return enrollment


# ============================================================
# 展位 - /api/admin/booths, /api/booths/*
# ============================================================

@admin_router.post(
    "/booths",
    response_model=BoothResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建展位（主办方）",
)
async def create_booth(
    data: BoothCreateRequest,
    current_user: CurrentUser = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exhibition).where(
            Exhibition.id == data.exhibition_id,
            Exhibition.organizer_id == current_user.user_id,
        )
    )
    exhibition = result.scalars().first()
    if not exhibition:
        raise HTTPException(status_code=404, detail="展会不存在或无权操作")

    result = await db.execute(
        select(Booth).where(
            Booth.exhibition_id == data.exhibition_id,
            Booth.booth_number == data.booth_number,
        )
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="展位编号已存在")

    booth = Booth(
        exhibition_id=data.exhibition_id,
        booth_number=data.booth_number,
        name=data.name,
        description=data.description,
        area=data.area,
        price=data.price,
        floor=data.floor,
        zone=data.zone,
        status=BoothStatus.AVAILABLE,
    )
    db.add(booth)
    exhibition.total_booths += 1
    exhibition.available_booths += 1

    await db.commit()
    await db.refresh(booth)
    return booth


@admin_router.get(
    "/stats",
    summary="全局统计数据（老板/主办方）",
)
async def get_admin_stats(
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(func.count(User.id)))
    total_users = result.scalar()

    result = await db.execute(select(func.count(Exhibition.id)))
    total_exhibitions = result.scalar()

    result = await db.execute(select(func.count(Booth.id)))
    total_booths = result.scalar()

    result = await db.execute(select(func.count(VisitorRegistration.id)))
    total_registrations = result.scalar()

    result = await db.execute(select(func.count(ExhibitionEnrollment.id)))
    total_enrollments = result.scalar()

    result = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    role_counts = result.all()

    return {
        "total_users": total_users,
        "total_exhibitions": total_exhibitions,
        "total_booths": total_booths,
        "total_registrations": total_registrations,
        "total_enrollments": total_enrollments,
        "user_role_distribution": {r.value: c for r, c in role_counts},
    }


# ============================================================
# 展商端展位路由 - /api/booths/*
# ============================================================

booth_router = APIRouter(prefix="/api/booths", tags=["展位管理"])


@booth_router.get(
    "",
    response_model=List[BoothResponse],
    summary="获取展位列表（公开）",
)
async def list_booths(
    exhibition_id: Optional[int] = Query(None, description="按展会筛选"),
    zone: Optional[str] = Query(None, description="按展区筛选"),
    status_param: Optional[str] = Query(None, alias="status", description="按状态筛选"),
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


@booth_router.post(
    "/book",
    response_model=BoothResponse,
    summary="预订展位（展商）",
)
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

    result = await db.execute(
        select(Booth).where(
            Booth.exhibitor_id == current_user.user_id,
            Booth.exhibition_id == booth.exhibition_id,
        )
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="您已在该展会拥有展位")

    booth.exhibitor_id = current_user.user_id
    booth.status = BoothStatus.RESERVED

    result = await db.execute(select(Exhibition).where(Exhibition.id == booth.exhibition_id))
    exhibition = result.scalars().first()
    if exhibition and exhibition.available_booths > 0:
        exhibition.available_booths -= 1

    await db.commit()
    await db.refresh(booth)
    return booth


# ============================================================
# 报名路由（游客）- /api/registrations/*
# ============================================================

registration_router = APIRouter(prefix="/api/registrations", tags=["报名管理"])


@registration_router.post(
    "",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="报名/收藏展会（游客）",
)
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


@registration_router.get(
    "/my",
    response_model=List[RegistrationResponse],
    summary="我的报名/收藏列表（游客）",
)
async def my_registrations_visitor(
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


# ============================================================
# 注册所有子路由
# ============================================================

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(exhibition_router)      # /api/exhibitions (含 /market)
router.include_router(exhibitor_router)        # /api/exhibitor/*
router.include_router(buyer_router)            # /api/buyer/*
router.include_router(procurement_router)      # /api/procurement/*
router.include_router(admin_router)            # /api/admin/*
router.include_router(booth_router)            # /api/booths/*
router.include_router(registration_router)     # /api/registrations/*
