"""
ExpoHub Pydantic 数据模型

包含：请求/响应序列化、数据验证、API 文档 Schema
"""

import re
from datetime import datetime
from typing import Optional, List, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from src.models import UserRole, UserStatus, Gender


# ============================================================
# 通用响应模型
# ============================================================

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应包装"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class ApiResponse(BaseModel):
    """统一 API 响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[dict | list] = None


class ErrorResponse(BaseModel):
    """错误响应体"""
    detail: str
    error_code: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {"detail": "用户名已存在", "error_code": "USERNAME_EXISTS"}
        }
    }


# ============================================================
# 认证相关
# ============================================================

class LoginRequest(BaseModel):
    """登录请求体"""
    username: str = Field(
        ..., min_length=3, max_length=50,
        description="用户名或邮箱",
        examples=["alice"],
    )
    password: str = Field(
        ..., min_length=1, max_length=128,
        description="密码",
        examples=["SecurePass123!"],
    )


class TokenResponse(BaseModel):
    """令牌响应体"""
    access_token: str = Field(..., description="访问令牌（短期）")
    refresh_token: str = Field(..., description="刷新令牌（长期）")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间（秒）")
    user: "UserProfileResponse" = Field(..., description="用户基本信息")


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求体"""
    refresh_token: str = Field(..., description="刷新令牌")


class RefreshTokenResponse(BaseModel):
    """刷新令牌响应体"""
    access_token: str = Field(..., description="新的访问令牌")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


# ============================================================
# 用户注册
# ============================================================

class RegisterRequest(BaseModel):
    """用户注册请求体"""
    username: str = Field(
        ..., min_length=3, max_length=50,
        description="用户名，3-50个字符，只能包含字母、数字、下划线和连字符",
        examples=["alice"],
    )
    email: str = Field(
        ..., description="邮箱地址",
        examples=["alice@example.com"],
    )
    password: str = Field(
        ..., min_length=8, max_length=128,
        description="密码，至少8个字符，需包含字母和数字",
        examples=["SecurePass123!"],
    )
    role: UserRole = Field(
        default=UserRole.VISITOR,
        description="用户角色：visitor(游客)/buyer(买家)/exhibitor(展商)/boss(老板)/organizer(主办方)",
    )
    nickname: Optional[str] = Field(
        None, max_length=100, description="昵称"
    )
    phone: Optional[str] = Field(
        None, pattern=r"^1[3-9]\d{9}$", description="手机号（11位）"
    )
    company: Optional[str] = Field(
        None, max_length=200, description="公司名称（展商/买家/主办方必填）"
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """用户名只能包含字母、数字、下划线和连字符"""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """验证邮箱格式"""
        pattern = r"^[\w.-]+@[\w.-]+\.\w+$"
        if not re.match(pattern, v):
            raise ValueError("邮箱格式不正确")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """密码必须包含字母和数字"""
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须包含至少一个字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含至少一个数字")
        return v

    @field_validator("company")
    @classmethod
    def validate_company(cls, v: Optional[str], info) -> Optional[str]:
        """展商、买家和主办方必须提供公司名称"""
        if info.data.get("role") in (UserRole.EXHIBITOR, UserRole.BUYER, UserRole.ORGANIZER) and not v:
            raise ValueError(f"{info.data.get('role').value} 角色必须提供公司名称")
        return v


class UserProfileResponse(BaseModel):
    """用户信息响应体"""
    id: int
    username: str
    email: str
    phone: Optional[str] = None
    role: UserRole
    status: UserStatus
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[Gender] = None
    company: Optional[str] = None
    position: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """用户信息更新请求体"""
    nickname: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
    gender: Optional[Gender] = None
    company: Optional[str] = Field(None, max_length=200)
    position: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=1000)
    phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$")


# ============================================================
# 展会相关
# ============================================================

class ExhibitionCreateRequest(BaseModel):
    """创建展会请求体"""
    name: str = Field(..., min_length=2, max_length=200, description="展会名称")
    short_name: Optional[str] = Field(None, max_length=50, description="展会简称")
    description: Optional[str] = Field(None, max_length=5000, description="展会描述")
    cover_url: Optional[str] = Field(None, max_length=500, description="封面图URL")
    start_date: datetime = Field(..., description="开始时间")
    end_date: datetime = Field(..., description="结束时间")
    registration_deadline: Optional[datetime] = Field(None, description="报名截止时间")
    venue: str = Field(..., min_length=2, max_length=200, description="举办场馆")
    address: str = Field(..., min_length=2, max_length=500, description="详细地址")
    city: str = Field(..., min_length=2, max_length=100, description="城市")
    total_booths: int = Field(default=0, ge=0, description="总展位数")

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: datetime, info) -> datetime:
        """结束时间必须在开始时间之后"""
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("结束时间必须在开始时间之后")
        return v


class ExhibitionResponse(BaseModel):
    """展会信息响应体"""
    id: int
    name: str
    short_name: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    start_date: datetime
    end_date: datetime
    registration_deadline: Optional[datetime] = None
    venue: str
    address: str
    city: str
    status: str
    organizer_id: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    reject_reason: Optional[str] = None
    total_booths: int
    available_booths: int
    visitor_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExhibitionListResponse(BaseModel):
    """展会列表项"""
    id: int
    name: str
    short_name: Optional[str] = None
    cover_url: Optional[str] = None
    start_date: datetime
    end_date: datetime
    venue: str
    city: str
    status: str
    total_booths: int
    available_booths: int
    visitor_count: int

    model_config = {"from_attributes": True}


# ============================================================
# 推荐展会市场（首页）
# ============================================================

class ExhibitionMarketResponse(BaseModel):
    """推荐展会市场响应 — 首页用"""
    id: int
    name: str
    short_name: Optional[str] = None
    cover_url: Optional[str] = None
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    venue: str
    city: str
    status: str
    total_booths: int
    available_booths: int
    visitor_count: int
    # 市场推荐扩展字段
    exhibitor_count: int = 0        # 已报名展商数
    buyer_count: int = 0            # 已注册买家数
    procurement_count: int = 0      # 采购需求数
    is_recommended: bool = False    # 是否推荐
    hot_category: Optional[str] = None  # 热门品类

    model_config = {"from_attributes": True}


# ============================================================
# 展位相关
# ============================================================

class BoothCreateRequest(BaseModel):
    """创建展位请求体"""
    exhibition_id: int = Field(..., description="所属展会ID")
    booth_number: str = Field(..., min_length=1, max_length=50, description="展位编号")
    name: Optional[str] = Field(None, max_length=200, description="展位名称")
    description: Optional[str] = Field(None, max_length=2000, description="展位描述")
    area: Optional[float] = Field(None, gt=0, description="展位面积（平方米）")
    price: Optional[float] = Field(None, ge=0, description="展位价格")
    floor: Optional[int] = Field(None, description="楼层")
    zone: Optional[str] = Field(None, max_length=50, description="展区")


class BoothResponse(BaseModel):
    """展位信息响应体"""
    id: int
    exhibition_id: int
    exhibitor_id: Optional[int] = None
    booth_number: str
    name: Optional[str] = None
    description: Optional[str] = None
    area: Optional[float] = None
    price: Optional[float] = None
    floor: Optional[int] = None
    zone: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BoothBookRequest(BaseModel):
    """预订展位请求体"""
    booth_id: int = Field(..., description="展位ID")


class BoothUpdateRequest(BaseModel):
    """更新展位资料请求体（展商更新自己的展位信息）"""
    name: Optional[str] = Field(None, max_length=200, description="展位名称")
    description: Optional[str] = Field(None, max_length=2000, description="展位描述")


# ============================================================
# 展会报名（展商报名 / 买家注册）
# ============================================================

class EnrollmentCreateRequest(BaseModel):
    """展会报名请求体 — 展商报名或买家注册"""
    exhibition_id: int = Field(..., description="展会ID")
    company_name: Optional[str] = Field(None, max_length=200, description="公司名称")
    contact_phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    remark: Optional[str] = Field(None, max_length=1000, description="备注/留言")


class EnrollmentResponse(BaseModel):
    """展会报名响应体"""
    id: int
    user_id: int
    exhibition_id: int
    enrollment_type: str
    status: str
    company_name: Optional[str] = None
    contact_phone: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # 关联的展会简要信息
    exhibition: Optional[ExhibitionListResponse] = None

    model_config = {"from_attributes": True}


class EnrollmentApprovalRequest(BaseModel):
    """审批报名请求体（主办方用）"""
    action: str = Field(..., description="审批动作: approve / reject")
    reject_reason: Optional[str] = Field(None, max_length=1000, description="驳回原因")


# ============================================================
# 报名相关（游客）
# ============================================================

class RegistrationCreateRequest(BaseModel):
    """报名/收藏展会请求体"""
    exhibition_id: int = Field(..., description="展会ID")
    is_favorite: bool = Field(default=False, description="是否收藏")
    is_registered: bool = Field(default=True, description="是否报名")


class RegistrationResponse(BaseModel):
    """报名信息响应体"""
    id: int
    visitor_id: int
    exhibition_id: int
    is_favorite: bool
    is_registered: bool
    ticket_code: Optional[str] = None
    check_in_at: Optional[datetime] = None
    created_at: datetime
    exhibition: Optional[ExhibitionListResponse] = None

    model_config = {"from_attributes": True}


# ============================================================
# 消息通知相关
# ============================================================

class MessageCreateRequest(BaseModel):
    """发送消息请求体"""
    receiver_id: int = Field(..., description="接收者用户ID")
    title: str = Field(..., min_length=1, max_length=200, description="消息标题")
    content: str = Field(..., min_length=1, max_length=5000, description="消息内容")


class MessageResponse(BaseModel):
    """消息响应体（完整）"""
    id: int
    sender_id: int
    receiver_id: int
    title: str
    content: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """消息列表项"""
    id: int
    sender_id: int
    sender_username: Optional[str] = None
    receiver_id: int
    receiver_username: Optional[str] = None
    title: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    """未读消息数响应"""
    unread_count: int


class ConversationResponse(BaseModel):
    """会话列表项"""
    other_user_id: int
    other_username: str
    other_avatar: Optional[str] = None
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    unread_count: int


# ============================================================
# 评价相关
# ============================================================

class ReviewCreateRequest(BaseModel):
    """提交评价请求体"""
    rating: int = Field(..., ge=1, le=5, description="评分 1-5 星")
    content: Optional[str] = Field(None, max_length=2000, description="评价内容")


class ReviewResponse(BaseModel):
    """评价响应体"""
    id: int
    user_id: int
    username: Optional[str] = None
    exhibition_id: int
    rating: int
    content: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RatingStatsResponse(BaseModel):
    """评分统计数据"""
    average_rating: float
    total_reviews: int
    distribution: dict  # {1: count, 2: count, 3: count, 4: count, 5: count}


# ============================================================
# 采购需求相关（必带 exhibition_id）
# ============================================================

class ProcurementCreateRequest(BaseModel):
    """创建采购需求请求体 — exhibition_id 必填"""
    exhibition_id: int = Field(..., description="关联展会ID（必填）")
    title: str = Field(..., min_length=2, max_length=200, description="采购标题")
    description: Optional[str] = Field(None, max_length=5000, description="需求详细描述")
    category: str = Field(..., min_length=1, max_length=100, description="采购品类")
    budget_min: Optional[float] = Field(None, ge=0, description="预算下限")
    budget_max: Optional[float] = Field(None, ge=0, description="预算上限")
    deadline: Optional[datetime] = Field(None, description="采购截止日期")

    @field_validator("budget_max")
    @classmethod
    def validate_budget(cls, v: Optional[float], info) -> Optional[float]:
        """预算上限不能低于下限"""
        budget_min = info.data.get("budget_min")
        if budget_min is not None and v is not None and v < budget_min:
            raise ValueError("预算上限不能低于预算下限")
        return v


class ProcurementUpdateRequest(BaseModel):
    """更新采购需求请求体"""
    title: Optional[str] = Field(None, min_length=2, max_length=200, description="采购标题")
    description: Optional[str] = Field(None, max_length=5000, description="需求详细描述")
    category: Optional[str] = Field(None, min_length=1, max_length=100, description="采购品类")
    budget_min: Optional[float] = Field(None, ge=0, description="预算下限")
    budget_max: Optional[float] = Field(None, ge=0, description="预算上限")
    deadline: Optional[datetime] = Field(None, description="采购截止日期")
    status: Optional[str] = Field(None, description="状态：pending/matched/completed/cancelled")


class ProcurementResponse(BaseModel):
    """采购需求响应体"""
    id: int
    visitor_id: int
    visitor_username: Optional[str] = None
    exhibition_id: int
    exhibition_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    deadline: Optional[datetime] = None
    status: str
    match_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProcurementMatchCreateRequest(BaseModel):
    """展商标记匹配采购需求请求体"""
    message: Optional[str] = Field(None, max_length=2000, description="展商留言/报价说明")
    quoted_price: Optional[float] = Field(None, ge=0, description="报价")


class ProcurementMatchResponse(BaseModel):
    """采购需求匹配响应体"""
    id: int
    procurement_id: int
    exhibitor_id: int
    exhibitor_username: Optional[str] = None
    exhibitor_company: Optional[str] = None
    message: Optional[str] = None
    quoted_price: Optional[float] = None
    is_accepted: Optional[bool] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 展品管理相关
# ============================================================

class ProductCreateRequest(BaseModel):
    """创建展品请求体"""
    booth_id: Optional[int] = Field(None, description="所属展位ID")
    exhibition_id: Optional[int] = Field(None, description="所属展会ID")
    name: str = Field(..., min_length=1, max_length=200, description="展品名称")
    description: Optional[str] = Field(None, max_length=5000, description="展品描述")
    category: str = Field(..., min_length=1, max_length=100, description="展品类目")
    images: Optional[List[str]] = Field(None, description="展品图片URL列表")
    price: Optional[float] = Field(None, ge=0, description="展品价格")
    specs: Optional[dict] = Field(None, description="展品规格参数")
    status: str = Field(default="draft", description="状态：draft/published/offline")


class ProductUpdateRequest(BaseModel):
    """更新展品请求体"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="展品名称")
    description: Optional[str] = Field(None, max_length=5000, description="展品描述")
    category: Optional[str] = Field(None, min_length=1, max_length=100, description="展品类目")
    images: Optional[List[str]] = Field(None, description="展品图片URL列表")
    price: Optional[float] = Field(None, ge=0, description="展品价格")
    specs: Optional[dict] = Field(None, description="展品规格参数")
    status: Optional[str] = Field(None, description="状态：draft/published/offline")
    booth_id: Optional[int] = Field(None, description="所属展位ID")


class ProductResponse(BaseModel):
    """展品响应体"""
    id: int
    exhibitor_id: int
    exhibitor_username: Optional[str] = None
    booth_id: Optional[int] = None
    exhibition_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    category: str
    images: Optional[List[str]] = None
    price: Optional[float] = None
    specs: Optional[dict] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# Dashboard 相关
# ============================================================

class ExhibitorDashboardResponse(BaseModel):
    """展商 Dashboard 概览"""
    my_booth_count: int
    registered_exhibition_count: int
    pending_booth_count: int  # 待处理的展位（如被预订等待确认）
    my_product_count: int
    total_matches: int  # 采购匹配数


class OrganizerDashboardResponse(BaseModel):
    """主办方 Dashboard 概览"""
    my_exhibition_count: int
    total_booth_count: int
    total_registration_count: int
    last_7_days_registrations: int
    last_7_days_booth_bookings: int


class AdminExhibitionStatsResponse(BaseModel):
    """主办方展会列表统计项"""
    id: int
    name: str
    status: str
    total_booths: int
    available_booths: int
    booked_booths: int
    visitor_count: int
    start_date: datetime
    end_date: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminRegistrationDetailResponse(BaseModel):
    """主办方查看报名详情"""
    id: int
    visitor_id: int
    visitor_username: Optional[str] = None
    visitor_email: Optional[str] = None
    is_favorite: bool
    is_registered: bool
    ticket_code: Optional[str] = None
    check_in_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminBoothAllocationResponse(BaseModel):
    """主办方查看展位分配"""
    id: int
    booth_number: str
    name: Optional[str] = None
    zone: Optional[str] = None
    price: Optional[float] = None
    status: str
    exhibitor_id: Optional[int] = None
    exhibitor_company: Optional[str] = None
    exhibitor_username: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================
# 展商个人中心 — 按展会自动分组
# ============================================================

class ExhibitorExhibitionGroup(BaseModel):
    """展商个人中心 — 按展会分组视图"""
    exhibition_id: int
    exhibition_name: str
    exhibition_cover: Optional[str] = None
    exhibition_status: str
    exhibition_city: str
    start_date: datetime
    end_date: datetime
    # 该展会下的展商数据
    booths: List[BoothResponse] = []
    products: List[ProductResponse] = []
    enrollment: Optional[EnrollmentResponse] = None
    procurement_matches: List[ProcurementMatchResponse] = []
    # 统计
    booth_count: int = 0
    product_count: int = 0
    match_count: int = 0


class ExhibitorCenterResponse(BaseModel):
    """展商个人中心完整响应"""
    total_exhibitions: int
    total_booths: int
    total_products: int
    total_matches: int
    groups: List[ExhibitorExhibitionGroup]


# ============================================================
# 数据报表相关
# ============================================================

class TrendDataPoint(BaseModel):
    """趋势数据点"""
    date: str
    value: int


class TrendResponse(BaseModel):
    """趋势数据响应"""
    dimension: str  # daily/weekly/monthly
    data: List[TrendDataPoint]


class StatsOverviewResponse(BaseModel):
    """完整统计数据响应"""
    total_users: int
    total_exhibitions: int
    total_booths: int
    total_registrations: int
    total_procurements: int
    total_products: int
    total_messages: int
    user_role_distribution: dict
    exhibition_status_distribution: dict
    procurement_status_distribution: dict
    exhibitor_active_count: int
    exhibitor_with_booth_count: int
    exhibitor_with_product_count: int
    procurement_total: int
    procurement_matched: int
    procurement_match_rate: float


class UserGrowthResponse(BaseModel):
    """用户增长趋势"""
    visitor_growth: List[TrendDataPoint]
    exhibitor_growth: List[TrendDataPoint]
    organizer_growth: List[TrendDataPoint]
    boss_growth: List[TrendDataPoint]
    total_growth: List[TrendDataPoint]


class ExhibitionTrendResponse(BaseModel):
    """展会数据趋势"""
    exhibition_created: List[TrendDataPoint]
    exhibition_published: List[TrendDataPoint]
    registrations: List[TrendDataPoint]


class ExhibitorActivityResponse(BaseModel):
    """展商活跃度统计"""
    total_exhibitors: int
    active_exhibitors: int
    with_products: int
    with_matches: int
    activity_rate: float


class ProcurementStatsResponse(BaseModel):
    """采购需求统计"""
    total: int
    pending: int
    matched: int
    completed: int
    cancelled: int
    match_rate: float
    completion_rate: float


# ============================================================
# 审核相关
# ============================================================

class ExhibitionApproveRequest(BaseModel):
    """展会审批请求体"""
    action: str = Field(..., description="审批动作：approve/reject")
    reject_reason: Optional[str] = Field(None, max_length=1000, description="驳回原因（驳回时必填）")

    @field_validator("reject_reason")
    @classmethod
    def validate_reject_reason(cls, v: Optional[str], info) -> Optional[str]:
        """驳回时必须提供原因"""
        if info.data.get("action") == "reject" and not v:
            raise ValueError("驳回时必须提供原因")
        return v


class AuditLogResponse(BaseModel):
    """审计日志响应体"""
    id: int
    user_id: Optional[int] = None
    user_role: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
