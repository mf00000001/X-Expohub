"""
认证路由（Auth）

端点：
- POST /auth/login          登录
- POST /auth/register       注册
- POST /auth/refresh        刷新令牌
- GET  /auth/profile        获取个人信息
- PUT  /auth/profile        更新个人信息
- PUT  /auth/password       修改密码
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    hash_password,
    verify_password,
)
from app.core.exceptions import BadRequest, Unauthorized, Conflict, NotFound
from app.models.base import get_db
from app.models.user import User
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/auth", tags=["认证"])


# ============================================================
# Pydantic Schemas
# ============================================================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """注册请求

    - visitor/buyer/exhibitor: 只需 username/email/password/role
    - organizer: 额外需要 company_name, business_license
    """
    username: str
    email: str
    password: str
    role: Optional[str] = "visitor"
    company_name: Optional[str] = None
    business_license: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"visitor", "buyer", "exhibitor", "organizer"}
        if v not in allowed:
            raise ValueError(f"不支持的角色类型: {v}，可选值: {', '.join(allowed)}")
        return v


class RefreshRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str


class ProfileUpdateRequest(BaseModel):
    """更新个人信息请求（所有字段可选）"""
    nickname: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[str] = None
    company: Optional[str] = None
    company_name: Optional[str] = None
    business_license: Optional[str] = None
    position: Optional[str] = None
    bio: Optional[str] = None
    # V2.0: 行业领域（展商用）
    industry_domain: Optional[str] = None
    sub_domains: Optional[str] = None


class InterestsUpdateRequest(BaseModel):
    """V2.0: 更新用户兴趣标签"""
    interests: list[str]  # 如 ["电子及家电", "AI/科技"]


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    """用户个人信息响应"""
    id: int
    username: str
    email: str
    phone: Optional[str] = None
    role: str
    status: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[str] = None
    company: Optional[str] = None
    company_name: Optional[str] = None
    business_license: Optional[str] = None
    organizer_status: Optional[str] = None
    position: Optional[str] = None
    bio: Optional[str] = None
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


# ============================================================
# 辅助函数
# ============================================================

def _user_to_profile(user: User) -> dict:
    """将 User 模型转为前端 profile 响应格式"""
    import json
    interests_list = None
    if user.interests:
        try:
            interests_list = json.loads(user.interests)
        except (json.JSONDecodeError, TypeError):
            interests_list = []
    sub_domains_list = None
    if user.sub_domains:
        try:
            sub_domains_list = json.loads(user.sub_domains)
        except (json.JSONDecodeError, TypeError):
            sub_domains_list = []
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "status": user.status,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "gender": user.gender,
        "company": user.company,
        "company_name": user.company_name,
        "business_license": user.business_license,
        "organizer_status": user.organizer_status,
        "position": user.position,
        "bio": user.bio,
        # V2.0
        "interests": interests_list,
        "is_onboarded": user.is_onboarded,
        "industry_domain": user.industry_domain,
        "sub_domains": sub_domains_list,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


# ============================================================
# 新人注册大礼包
# ============================================================

def _welcome_bonus(user, db):
    """新用户注册赠送：50积分 + 7天普通会员"""
    from datetime import timedelta
    from app.models.points import PointsLedger
    from app.models.membership import Membership, TIER_PRODUCT_LIMITS

    now = datetime.now(timezone.utc)

    # 送50积分
    user.total_points = 50
    ledger = PointsLedger(
        user_id=user.id,
        transaction_type="bonus_welcome",
        amount=50,
        balance_after=50,
        description="🎁 新人注册礼包 +50分",
    )
    db.add(ledger)

    # 送7天普通会员（仅展商和买家）
    if user.role in ("exhibitor", "buyer"):
        membership = Membership(
            user_id=user.id,
            tier="regular",
            product_limit=TIER_PRODUCT_LIMITS["regular"],
            expires_at=now + timedelta(days=7),
        )
        db.add(membership)

    db.commit()


# ============================================================
# 端点
# ============================================================

@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """用户登录

    返回 access_token 和 refresh_token。
    """
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise Unauthorized(message="用户名或密码错误")

    if not verify_password(data.password, user.password_hash):
        raise Unauthorized(message="用户名或密码错误")

    if user.status == "banned":
        raise Unauthorized(message="账号已被封禁")

    # 主办方被驳回不允许登录
    if user.role == "organizer" and user.organizer_status == "rejected":
        raise Unauthorized(message="主办方入驻申请已被驳回，请联系平台管理员")

    # 生成双令牌
    token_data = {"sub": user.id, "role": user.role, "ver": user.token_version or 0}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "登录成功",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": _user_to_profile(user),
        },
    }


@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册

    - 普通用户（visitor/buyer/exhibitor）注册后状态为 active
    - 主办方（organizer）注册后状态为 active，但 organizer_status = pending，需平台管理员审核
    """
    # 检查用户名唯一性
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise Conflict(message="用户名已被注册")

    # 检查邮箱唯一性
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise Conflict(message="邮箱已被注册")

    # 主办方必须提供公司名称和营业执照
    if data.role == "organizer":
        if not data.company_name:
            raise BadRequest(message="主办方注册需要提供公司名称（company_name）")
        if not data.business_license:
            raise BadRequest(message="主办方注册需要提供营业执照图片URL（business_license）")

    # 创建用户
    import uuid
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role or "visitor",
        status="active",
        nickname=data.username,
        company_name=data.company_name,
        business_license=data.business_license,
        organizer_status="pending" if data.role == "organizer" else None,
        referral_code=uuid.uuid4().hex[:8].upper(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # V2.2: 新人注册大礼包
    _welcome_bonus(user, db)

    # 注册成功直接生成令牌
    token_data = {"sub": user.id, "role": user.role, "ver": user.token_version or 0}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return {
        "success": True,
        "code": "OK",
        "message": "注册成功" + ("，主办方入驻申请已提交，等待管理员审核" if data.role == "organizer" else ""),
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": _user_to_profile(user),
            "welcome_bonus": {
                "points": 50,
                "membership": "7天普通会员免费体验",
                "message": "🎁 新人礼包：50积分已到账 + 7天普通会员体验！快去创建微展位吧",
            },
        },
    }


@router.post("/refresh")
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    """刷新 Access Token

    使用 refresh_token 换取新的 access_token。
    """
    try:
        payload = verify_token(data.refresh_token)
    except ValueError as e:
        raise Unauthorized(message=f"Refresh Token 无效: {e}")

    if payload.get("type") != "refresh":
        raise Unauthorized(message="请使用 Refresh Token")

    user_id = payload.get("sub")
    if not user_id:
        raise Unauthorized(message="令牌无效：缺少用户标识")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise Unauthorized(message="用户不存在")

    # 状态校验：禁用/封禁用户不允许续期
    if user.status != "active":
        raise Unauthorized(message="账号已被禁用或封禁，无法续期")

    # V3.2: 令牌版本校验(登出后旧 refresh token 失效)
    if payload.get("ver") != (user.token_version or 0):
        raise Unauthorized(message="令牌已失效，请重新登录")

    # 生成新令牌
    token_data = {"sub": user.id, "role": user.role, "ver": user.token_version or 0}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return {
        "success": True,
        "code": "OK",
        "message": "令牌刷新成功",
        "data": {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        },
    }


@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_active_user)):
    """获取当前登录用户的个人信息"""
    return {
        "success": True,
        "code": "OK",
        "message": "获取成功",
        "data": _user_to_profile(current_user),
    }


@router.put("/profile")
def update_profile(
    data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """更新当前用户的个人信息（部分更新）"""
    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if hasattr(current_user, field):
            setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "code": "OK",
        "message": "个人信息更新成功",
        "data": _user_to_profile(current_user),
    }


@router.put("/password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """修改密码"""
    if not verify_password(data.old_password, current_user.password_hash):
        raise BadRequest(message="原密码错误")

    current_user.password_hash = hash_password(data.new_password)
    db.commit()

    return {
        "success": True,
        "code": "OK",
        "message": "密码修改成功",
        "data": None,
    }


# ============================================================
# V2.0: 兴趣引导
# ============================================================

@router.put("/interests")
def update_interests(
    data: InterestsUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """保存用户兴趣标签（新用户引导 / 设置页修改）

    前端调用：PUT /auth/interests
    请求体：{"interests": ["电子及家电", "照明"]}
    """
    import json

    if not data.interests or len(data.interests) == 0:
        raise BadRequest(message="请至少选择一个兴趣领域")

    if len(data.interests) > 5:
        raise BadRequest(message="最多选择5个兴趣领域")

    current_user.interests = json.dumps(data.interests, ensure_ascii=False)
    current_user.interest_selected_at = datetime.now(timezone.utc)
    current_user.is_onboarded = True
    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "code": "OK",
        "message": "兴趣保存成功",
        "data": _user_to_profile(current_user),
    }

@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """登出: 递增令牌版本, 使该用户所有已发 token(含 refresh)立即失效"""
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()
    return {"success": True, "code": "OK", "message": "已安全登出", "data": None}
