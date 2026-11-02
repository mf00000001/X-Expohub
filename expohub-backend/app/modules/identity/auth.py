"""
认证路由（Auth）

端点：
- POST   /auth/login          登录
- POST   /auth/register       注册
- POST   /auth/refresh        刷新令牌
- GET    /auth/profile        获取个人信息
- PUT    /auth/profile        更新个人信息
- PUT    /auth/password       修改密码
- GET    /auth/export         导出我的个人数据（查阅权 / 复制权）
- DELETE /auth/account        注销账号（软删除 + 匿名化，删除权 / 撤回同意）

个人信息保护合规依据（《中华人民共和国个人信息保护法》，PIPL）：
- 第 45 条（查阅、复制权）：个人有权向个人信息处理者查阅、复制其个人信息。
  对应 `GET /auth/export`——只导出本人数据，JSON 可直接复制/保存，
  不含密码哈希、令牌，也不含任何他人信息。
- 第 47 条（删除权）：个人请求删除时，处理者应当主动删除个人信息。
  技术上以「软删除 + 匿名化」实现（见 `DELETE /auth/account`）：
  账号被置为 disabled 从而无法再使用任何需登录的业务功能，可识别字段全部置空或替换为不可回溯的值，
  同时保留不含身份标识的业务记录以满足统计口径与交易凭证留存义务。
- 第 15 条（撤回同意）：个人有权撤回同意，撤回后处理者应当停止处理。
  注销时清除 `privacy_agreed_at`（同意留痕）与 `interests`（画像标签）并
  递增 `token_version` 使已发令牌立即失效；个性化推荐开关见 `PUT /auth/preferences`
  （第 24 条自动化决策选择权）。
"""

import importlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    hash_password,
    verify_password,
)
from app.core.exceptions import BadRequest, Unauthorized, Conflict, NotFound, Forbidden
from app.models.base import get_db
from app.models.user import User
from app.core.deps import get_current_active_user, get_current_user

router = APIRouter(prefix="/auth", tags=["认证"])

logger = logging.getLogger(__name__)


# ============================================================
# Pydantic Schemas
# ============================================================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """注册请求

    - 仅 visitor/buyer/exhibitor 自助注册（2026-10-19 起取消 organizer 角色）
    - company_name / business_license 保留给展商资质，可在注册时选填
    """
    username: str
    email: str
    password: str
    role: Optional[str] = "visitor"
    company_name: Optional[str] = None
    business_license: Optional[str] = None
    # 2026-10-19 合规：必须显式同意《用户协议》《隐私政策》（不默认勾选）
    privacy_agreed: bool = False

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"visitor", "buyer", "exhibitor"}
        if v not in allowed:
            raise ValueError(f"不支持的角色类型: {v}，可选值: {', '.join(sorted(allowed))}（admin 由后台开通）")
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
        "personalized_recommend": bool(getattr(user, "personalized_recommend", True)),
        "privacy_agreed_at": user.privacy_agreed_at.isoformat() if getattr(user, "privacy_agreed_at", None) else None,
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

    # 安全硬化：登录拦截改为「白名单」口径——只有 status == 'active' 才放行。
    # 为什么不再逐个枚举 banned/disabled：users.status 的默认值是 'pending'
    # （见 models/user.py 的 status 列），旧写法漏掉了 pending，
    # 于是待审核账号能登录拿到 token，但 get_current_active_user 要求
    # status == 'active'，导致每个业务接口都 403 —— 语义不一致。
    # 白名单写法让「以后新增的状态」默认被拒绝，而不是默认放行。
    # 提示语口径：
    # - banned 保留既有「账号已被封禁」，兼容前端/客服既有文案；
    # - pending / disabled / 其它未知状态统一用中性措辞，
    #   不暴露账号当前具体处于哪种状态（避免被用来探测账号状态）。
    if user.status == "banned":
        raise Unauthorized(message="账号已被封禁")

    if user.status != "active":
        raise Unauthorized(message="账号不可用或待审核，请联系平台管理员")

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
    """用户注册（两方撮合模型）

    compliance: 必须显式传 privacy_agreed=true（前端勾选框不默认勾选），
    否则拒绝注册；同意时间写入 privacy_agreed_at 留痕。

    - visitor / buyer / exhibitor 注册后状态为 active
    - 平台运营账号（admin，含展会自营）只能由后台开通，不开放自助注册
    - 用户名不可占用 deleted_ 前缀、邮箱域名不可为 deleted.local（已注销账号的
      匿名化标识，见下方「PIPL 个人信息权利」区块）
    """
    if not data.privacy_agreed:
        raise BadRequest(message="请先阅读并同意《用户协议》与《隐私政策》后再注册")

    # 安全硬化：保留「已注销账号」的匿名化命名，禁止自助注册占用。
    # 否则可以先注册 deleted_xxx 用户名 / @deleted.local 邮箱，冒充已注销账号
    # （lookalike），干扰注销幂等判断与后台审计识别。
    # 匹配规则只针对前缀与「完整域名」，因此 deletedfoo、a@deleted.local.cn
    # 这类正常用户名/邮箱不受影响：
    # - 用户名不区分大小写，判断的是开头是否为 deleted_；
    # - 邮箱判断结尾是否为 "@deleted.local"（域名必须完全等于 deleted.local）。
    # 两个标记常量统一定义在文件下方「PIPL 个人信息权利」区块，避免两处各写一份。
    if (data.username or "").lower().startswith(_DELETED_USERNAME_PREFIX):
        raise BadRequest(message="该用户名不可用")
    if (data.email or "").lower().endswith(_DELETED_EMAIL_DOMAIN):
        raise BadRequest(message="该邮箱不可用")

    # 检查用户名唯一性
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise Conflict(message="用户名已被注册")

    # 检查邮箱唯一性
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise Conflict(message="邮箱已被注册")

    # 2026-10-19：取消 organizer 角色后，注册不再需要主办方资质；
    # 展商资质（company_name / business_license）改为选填，由后台审核。

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
        organizer_status=None,
        privacy_agreed_at=datetime.now(timezone.utc),
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
        "message": "注册成功",
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

    # 2026-10-19：允许清空（算法推荐规定第 17 条：用户应能删除用于推荐的特征标签）
    if data.interests is not None and len(data.interests) > 5:
        raise BadRequest(message="最多选择5个兴趣领域")

    if not data.interests:
        current_user.interests = None
        current_user.interest_selected_at = datetime.now(timezone.utc)
        current_user.is_onboarded = True
        db.commit()
        db.refresh(current_user)
        return {
            "success": True,
            "code": "OK",
            "message": "兴趣标签已清空",
            "data": _user_to_profile(current_user),
        }

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

class PreferencesUpdateRequest(BaseModel):
    """推荐偏好（2026-10-19 合规）"""
    personalized_recommend: bool


@router.put("/preferences")
def update_preferences(
    data: PreferencesUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """开关个性化推荐（PIPL 第 24 条 / 算法推荐规定第 17 条）

    关闭后：推荐接口改为按最新/热度排序（见 modules/matching/recommendations.py），
    不再使用展商画像与兴趣标签。
    """
    current_user.personalized_recommend = bool(data.personalized_recommend)
    db.commit()
    db.refresh(current_user)
    return {
        "success": True,
        "code": "OK",
        "message": "已开启个性化推荐" if data.personalized_recommend else "已关闭个性化推荐，将按最新内容排序",
        "data": {
            "personalized_recommend": bool(current_user.personalized_recommend),
        },
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


# ============================================================
# PIPL 个人信息权利：查阅/复制（第 45 条）、删除/注销（第 47 条、第 15 条）
# ============================================================

# 导出时单表最多返回的行数（积分账本按需求固定最近 200 条）
_EXPORT_ROW_LIMIT = 200

# 注销后账号的固定匿名化标记：既作为幂等判断依据，也便于后台审计识别
_DELETED_USERNAME_PREFIX = "deleted_"
_DELETED_EMAIL_DOMAIN = "@deleted.local"


def _import_optional_models(*specs: tuple) -> dict:
    """按需导入模型，返回 {类名: 模型类 或 None}

    导出接口要覆盖「可能存在、也可能尚未启用」的模型（例如票务域），
    因此逐个 import：任何模块/类不存在都只让该数据块降级为 None，
    而不是让整个导出接口 500（PIPL 第 45 条的查阅权不应被单表缺失阻断）。
    """
    models: dict = {}
    for module_path, class_name in specs:
        try:
            module = importlib.import_module(module_path)
            models[class_name] = getattr(module, class_name)
        except Exception as exc:  # noqa: BLE001 - 模型缺失不影响导出
            logger.warning(
                "[auth/export] 模型 %s.%s 不可用，已跳过该数据块: %s",
                module_path, class_name, exc,
            )
            models[class_name] = None
    return models


def _row_to_dict(row) -> dict:
    """把一行 ORM 对象转成 dict（只取本表列，datetime 转 ISO 8601 字符串）

    只遍历 row.__table__.columns，不展开任何 relationship，
    因此不会顺带查询关联表（也就不会带出他人数据），
    输出完全等价于「这一行」本身。
    """
    data = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name, None)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


def _collect_own_rows(
    db: Session,
    label: str,
    model,
    filter_fn,
    order_column: Optional[str] = None,
    descending: bool = True,
    limit: Optional[int] = None,
) -> list:
    """查询「只属于本人」的数据并序列化；模型缺失或单表查询失败时降级为 []

    Args:
        label: 日志用数据块名（如 points_ledger）
        model: 模型类；None 表示该模型不存在（直接跳过）
        filter_fn: 接收模型类，返回「本人」条件的 SQLAlchemy 表达式。
                   每个数据块都必须带 user_id / visitor_id 等归属字段过滤，
                   禁止无过滤全表查询（越权防线之一）。
        order_column: 排序列名（可选）
        limit: 返回行数上限（可选）

    说明：单表失败只降级为空列表并记日志，不影响其余数据块的导出。
    """
    if model is None:
        return []
    try:
        query = db.query(model).filter(filter_fn(model))
        if order_column is not None:
            column = getattr(model, order_column)
            query = query.order_by(column.desc() if descending else column.asc())
        if limit:
            query = query.limit(limit)
        return [_row_to_dict(row) for row in query.all()]
    except Exception as exc:  # noqa: BLE001 - 单表失败不影响整体导出
        logger.warning("[auth/export] 数据块 %s 查询失败，已降级为空: %s", label, exc)
        # SQLite 上失败的 SELECT 会让当前事务失效，回滚以便后续数据块继续查询
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return []


def _is_anonymized(user: User) -> bool:
    """账号是否已执行过注销匿名化（status=disabled + username/email 均为匿名值）

    三个条件同时成立才认定为「已注销」，避免有人注册一个 deleted_ 开头的用户名
    或 deleted.local 域邮箱就骗过注销接口拿到「假成功」。
    """
    return (
        (user.status or "") == "disabled"
        and (user.username or "").startswith(_DELETED_USERNAME_PREFIX)
        and (user.email or "").endswith(_DELETED_EMAIL_DOMAIN)
    )


async def _get_current_user_for_erasure(
    current_user: User = Depends(get_current_user),
) -> User:
    """注销接口专用鉴权：在 get_current_active_user 语义上多放行「已注销重试」

    为什么不能直接复用 get_current_active_user：
    注销会把 status 置为 disabled，而该依赖要求 status == 'active'，
    于是「第二次注销」会被 403 挡住，无法满足幂等要求。
    这里保持等价的安全语义：
    - status == 'active'                     → 正常注销流程；
    - status == 'disabled' 且已匿名化         → 已注销账号的幂等重试，返回同样的成功；
    - 被管理员禁用/封禁但未匿名化              → 仍然 403，不放开。
    """
    if current_user.status == "active":
        return current_user
    if _is_anonymized(current_user):
        return current_user
    raise Forbidden(message="账号已被禁用或待审核，请联系管理员")


@router.get("/export")
def export_my_data(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """导出当前登录用户的个人数据（PIPL 第 45 条：查阅权、复制权）

    合规要点：
    - 仅限本人：所有查询都以 current_user.id 作为归属条件，接口不接受
      任何请求参数里的 user_id / 表名 / 分页项，因此没有越权读取他人数据的入口；
    - 不返回密码哈希（password_hash）、token（access/refresh/token_version）
      以及任何他人信息；
    - 返回 dict，FastAPI 默认以 JSONResponse 输出
      （Content-Type: application/json; charset=utf-8），可下载保存。

    覆盖数据块：profile、interests、memberships、points_ledger（最近 200 条）、
    registrations、procurements（本人发布）、favorites、reviews（本人撰写）、
    appointments（本人相关：作为买家或展商）、tickets（本人订单 + 入场券，模型存在时）。
    """
    uid = current_user.id

    # profile 先序列化：后面若某数据块查询失败会 rollback，回滚会让 current_user
    # 的属性过期（再次访问需重新查库），先取值可避免额外查询。
    profile = _user_to_profile(current_user)

    # 显式确认模型存在后再查询（票务域按需加载，缺失则对应数据块为空）
    models = _import_optional_models(
        ("app.models.membership", "Membership"),
        ("app.models.points", "PointsLedger"),
        ("app.models.registration", "Registration"),
        ("app.models.procurement", "Procurement"),
        ("app.models.favorite", "Favorite"),
        ("app.models.review", "Review"),
        ("app.models.appointment", "Appointment"),
        ("app.modules.ticketing.models", "TicketingOrder"),
        ("app.modules.ticketing.models", "Ticket"),
    )

    data = {
        # 基本资料（复用 profile 序列化，天然不含 password_hash / token）
        "profile": profile,
        # 兴趣标签（画像数据，已在 profile 中解析为数组，此处单独列一份便于阅读）
        "interests": profile.get("interests") or [],
        # 会员订阅
        "memberships": _collect_own_rows(
            db, "memberships", models["Membership"],
            lambda m: m.user_id == uid,
        ),
        # 积分账本：最近 200 条（按时间倒序）
        "points_ledger": _collect_own_rows(
            db, "points_ledger", models["PointsLedger"],
            lambda m: m.user_id == uid,
            order_column="created_at",
            descending=True,
            limit=_EXPORT_ROW_LIMIT,
        ),
        # 展会报名（本人报名记录，含电子票码）
        "registrations": _collect_own_rows(
            db, "registrations", models["Registration"],
            lambda m: m.visitor_id == uid,
        ),
        # 本人发布的采购需求
        "procurements": _collect_own_rows(
            db, "procurements", models["Procurement"],
            lambda m: m.purchaser_id == uid,
        ),
        # 本人收藏
        "favorites": _collect_own_rows(
            db, "favorites", models["Favorite"],
            lambda m: m.user_id == uid,
        ),
        # 本人撰写的评价
        "reviews": _collect_own_rows(
            db, "reviews", models["Review"],
            lambda m: m.reviewer_id == uid,
        ),
        # 本人相关的预约：既可能是买家（buyer_id），也可能是展商（exhibitor_id）
        "appointments": _collect_own_rows(
            db, "appointments", models["Appointment"],
            lambda m: or_(m.buyer_id == uid, m.exhibitor_id == uid),
        ),
        # 票务域（P3）：本人订单 + 本人入场券，均为 TicketingOrder.user_id / Ticket.user_id
        "tickets": {
            "orders": _collect_own_rows(
                db, "tickets.orders", models["TicketingOrder"],
                lambda m: m.user_id == uid,
                order_column="created_at",
                descending=True,
            ),
            "tickets": _collect_own_rows(
                db, "tickets.tickets", models["Ticket"],
                lambda m: m.user_id == uid,
                order_column="created_at",
                descending=True,
            ),
        },
        # 导出时点（快照说明，不含他人信息）
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "success": True,
        "code": "OK",
        "message": "导出成功",
        "data": data,
    }


@router.delete("/account")
def delete_my_account(
    current_user: User = Depends(_get_current_user_for_erasure),
    db: Session = Depends(get_db),
):
    """注销账号：软删除 + 匿名化（PIPL 第 47 条删除权、第 15 条撤回同意）

    为什么是「软删除 + 匿名化」而不是物理 DELETE：
    - 保留统计口径：用户数、报名数、积分流水、成交等历史指标不会因注销而塌陷；
    - 保留对方可见性：买家/展商的历史预约、评价、采购、订单对相对方仍然成立，
      但 users 表中已不含任何可识别身份字段；
    - 幂等：已注销（status=disabled 且已匿名化）的账号再次调用，直接返回
      同样的成功响应，不重复处理、不报错。

    具体动作（只写 users 表中本人这一行）：
    - status='disabled'（立即失去 active 语义，业务接口鉴权全部拒绝）；
    - username=f"deleted_{id}_{随机6位}"、email=f"deleted_{id}@deleted.local"、
      phone=None、nickname='已注销用户'、avatar_url=None、bio=None、
      company=None、company_name=None、business_license=None、
      interests=None、privacy_agreed_at=None（撤回同意，同意留痕一并清除）；
    - token_version += 1（所有已发 access/refresh token 立即失效）；
    - password_hash 保持原值不改。已注销账号无法再登录：login() 采用白名单口径，
      只有 status=='active' 放行，'disabled' 与其它非 active 状态一律拒绝
      （'banned' 保留「账号已被封禁」，其余状态统一中性提示，不暴露账号状态），
      即便拿到历史 token，业务接口仍会被 get_current_active_user 以 403 拒绝。

    不删除的业务数据：products / micro_booths / procurements / reviews /
    appointments / registrations / ticketing_orders / tickets 全部保留。
    冗余可识别字段（products.exhibitor_name、booths.exhibitor_name、
    micro_booths.name、appointments.buyer_name / exhibitor_name、
    procurements.purchaser_name、reviews.reviewer_name）**保持原样、不脱敏**，理由：
    1) 它们是下单/预约/评价成交时的展示名快照，一旦改成「已注销展商」，
       会让相对方的历史记录出现假信息，影响对账与纠纷处理；
    2) 本质是「商户/公司展示名」而非账号标识，users 表的
       username / email / phone 已清除，无法再反查到自然人；
    3) PIPL 第 47 条允许在法定/约定保存期限内保留必要记录，交易凭证属于此类。
    若后续要求更严格（例如自然人展商注销），可另做批量脱敏脚本把它们置为
    「已注销展商」——本次未做，避免在注销事务里跨表批量写放大风险。
    """
    uid = current_user.id

    # ---- 幂等：已注销（已匿名化）的账号直接返回同样的成功响应 ----
    if _is_anonymized(current_user):
        return {
            "success": True,
            "code": "OK",
            "message": "账号已注销（已匿名化处理）",
            "data": None,
        }

    # 随机 6 位后缀（secrets 强随机），避免与唯一约束冲突、也避免被猜测复用
    suffix = secrets.token_hex(3)

    # ---- 1) 软删除标记 ----
    current_user.status = "disabled"

    # ---- 2) 匿名化：可识别到「这个人」的字段全部删除或替换 ----
    current_user.username = f"{_DELETED_USERNAME_PREFIX}{uid}_{suffix}"
    current_user.email = f"deleted_{uid}{_DELETED_EMAIL_DOMAIN}"
    current_user.phone = None
    current_user.nickname = "已注销用户"
    current_user.avatar_url = None
    current_user.bio = None
    current_user.company = None
    current_user.company_name = None
    current_user.business_license = None
    # 兴趣标签属于画像数据，注销时一并清除（第 15 条撤回同意后停止处理）
    current_user.interests = None
    # 同意留痕清除：撤回同意后不再保留「曾同意处理」的凭据
    current_user.privacy_agreed_at = None

    # ---- 3) 令牌失效：已发 access/refresh token 立即作废 ----
    current_user.token_version = (current_user.token_version or 0) + 1

    db.commit()
    # 写操作审计中间件（app/core/audit.py）会以
    # action="DELETE /api/auth/account" 自动留痕，无需在此额外写审计表
    logger.info("[auth/account] 用户 %s 已注销并完成匿名化", uid)

    return {
        "success": True,
        "code": "OK",
        "message": "账号已注销（已匿名化处理）",
        "data": None,
    }
