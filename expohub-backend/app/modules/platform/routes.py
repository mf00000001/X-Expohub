"""
平台运营域路由（P6 新增，前缀 /api/platform）

- GET  /plans                         档位列表（公开）
- POST /plans                         创建/更新档位（管理员）
- GET  /me/plan                       我的订阅 + 用量快照
- PUT  /tenants/{tenant_id}/plan      分配订阅（管理员）
- POST /import/exhibitions            批量导入展会（主办方/管理员；标题去重、逐行校验）
- GET  /overview                      平台总览（管理员）

设计：全部为新增能力，不触碰存量端点；导入走模型级校验，失败逐行报告不整体回滚。
"""
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_active_user, require_permission
from app.core.exceptions import BadRequest
from app.core.permissions import Permission
from app.models.base import get_db, SessionLocal
from app.models.exhibition import Exhibition
from app.models.user import User
from app.modules.platform.models import TenantPlan, TenantSubscription
from app.modules.ticketing.models import TicketingOrder, Ticket
from app.modules.onsite.models import OnsiteCheckinLog

router = APIRouter(prefix="/platform", tags=["平台运营"])


def _default_plan() -> dict:
    return {"tier": "basic", "name": "基础版", "monthly_fee_cents": 0, "features": []}


def _plan_view(p: TenantPlan) -> dict:
    return {"id": p.id, "tier": p.tier, "name": p.name,
            "monthly_fee_cents": p.monthly_fee_cents,
            "features": json.loads(p.features_json or "[]"),
            "active": p.active}


def _current_plan(db: Session, tenant_id: str) -> dict:
    sub = db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id).first()
    if sub:
        plan = db.query(TenantPlan).filter(TenantPlan.id == sub.plan_id).first()
        if plan:
            return _plan_view(plan)
    return _default_plan()


# ============================================================
# Schemas
# ============================================================

class PlanUpsert(BaseModel):
    tier: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=100)
    monthly_fee_cents: int = Field(0, ge=0)
    features: list[str] = Field(default_factory=list)


class AssignPlanRequest(BaseModel):
    plan_id: int


class ExhibitionImportRow(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    start_date: str = Field(..., min_length=8)
    end_date: str = Field(..., min_length=8)
    location: str = Field(..., min_length=1, max_length=300)
    status: str = "draft"
    description: str | None = None
    cover_image: str | None = None


class ExhibitionImportRequest(BaseModel):
    rows: list[ExhibitionImportRow] = Field(..., min_length=1, max_length=2000)


# ============================================================
# 档位计费
# ============================================================

@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    """公开：在售档位列表"""
    plans = db.query(TenantPlan).filter(TenantPlan.active.is_(True)).order_by(TenantPlan.id).all()
    return {"success": True, "code": "OK", "message": "获取成功", "data": {
        "list": [_plan_view(p) for p in plans],
    }}


@router.post("/plans")
def upsert_plan(
    data: PlanUpsert,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.PLATFORM_MANAGE)),
):
    """管理员：按 tier 创建或更新档位"""
    plan = db.query(TenantPlan).filter(TenantPlan.tier == data.tier).first()
    if plan:
        plan.name = data.name
        plan.monthly_fee_cents = data.monthly_fee_cents
        plan.features_json = json.dumps(data.features, ensure_ascii=False)
    else:
        plan = TenantPlan(tier=data.tier, name=data.name,
                          monthly_fee_cents=data.monthly_fee_cents,
                          features_json=json.dumps(data.features, ensure_ascii=False))
        db.add(plan)
    db.commit()
    db.refresh(plan)
    return {"success": True, "code": "OK", "message": "档位已保存", "data": _plan_view(plan)}


@router.get("/me/plan")
def my_plan(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """我的订阅 + 用量快照"""
    tenant_id = settings.TENANT_DEFAULT
    plan = _current_plan(db, tenant_id)
    usage = {
        "exhibitions_count": db.query(Exhibition).count(),
        "orders_count": db.query(TicketingOrder).count(),
        "tickets_count": db.query(Ticket).count(),
        "checkin_logs_count": db.query(OnsiteCheckinLog).count(),
    }
    return {"success": True, "code": "OK", "message": "获取成功", "data": {
        "tenant_id": tenant_id, "plan": plan, "usage": usage,
    }}


@router.put("/tenants/{tenant_id}/plan")
def assign_plan(
    tenant_id: str,
    data: AssignPlanRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.PLATFORM_MANAGE)),
):
    """管理员：为租户分配订阅档位（不存在则新建）"""
    plan = db.query(TenantPlan).filter(TenantPlan.id == data.plan_id).first()
    if not plan:
        raise BadRequest(message="档位不存在")
    sub = db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id).first()
    if sub:
        sub.plan_id = plan.id
        sub.status = "active"
    else:
        sub = TenantSubscription(tenant_id=tenant_id, plan_id=plan.id)
        db.add(sub)
    db.commit()
    return {"success": True, "code": "OK", "message": "订阅已更新",
            "data": {"tenant_id": tenant_id, "plan": _plan_view(plan)}}


# ============================================================
# 数据导入（展会）→ 复用闭环
# ============================================================

@router.post("/import/exhibitions")
def import_exhibitions(
    data: ExhibitionImportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.EXHIBITION_CREATE)),
):
    """批量导入展会：标题去重（同租户），逐行校验，失败行报告不阻断其他行"""
    existing = {e.title for e in db.query(Exhibition).all()}
    results = []
    ok = 0
    for i, row in enumerate(data.rows):
        if row.title in existing:
            results.append({"row": i + 1, "title": row.title, "ok": False, "reason": "标题重复，已跳过"})
            continue
        if row.status not in ("draft", "pending", "published", "registering", "live", "ended", "cancelled"):
            results.append({"row": i + 1, "title": row.title, "ok": False, "reason": f"非法状态: {row.status}"})
            continue
        try:
            db.add(Exhibition(
                title=row.title, start_date=row.start_date, end_date=row.end_date,
                location=row.location, status=row.status, description=row.description,
                cover_image=row.cover_image,
            ))
            db.commit()
            existing.add(row.title)
            ok += 1
            results.append({"row": i + 1, "title": row.title, "ok": True, "reason": "已导入"})
        except Exception as exc:  # 逐行失败不阻断
            db.rollback()
            results.append({"row": i + 1, "title": row.title, "ok": False, "reason": f"导入失败: {str(exc)[:80]}"})
    return {"success": True, "code": "OK",
            "message": f"导入完成：成功 {ok}/{len(data.rows)}", "data": {
                "success_count": ok, "total": len(data.rows), "results": results,
            }}


# ============================================================
# 平台总览
# ============================================================

@router.get("/overview")
def platform_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.PLATFORM_MANAGE)),
):
    """平台总览：核心业务计数（运营看板）"""
    from app.core.audit import AuditLog
    from app.models.user import User as UserModel
    overview = {
        "users_count": db.query(UserModel).count(),
        "exhibitions_count": db.query(Exhibition).count(),
        "orders_count": db.query(TicketingOrder).count(),
        "paid_orders_count": db.query(TicketingOrder).filter(TicketingOrder.status == "paid").count(),
        "tickets_count": db.query(Ticket).count(),
        "checkin_logs_count": db.query(OnsiteCheckinLog).count(),
        "audit_logs_count": db.query(AuditLog).count(),
        "plans_count": db.query(TenantPlan).count(),
    }
    return {"success": True, "code": "OK", "message": "获取成功", "data": overview}
