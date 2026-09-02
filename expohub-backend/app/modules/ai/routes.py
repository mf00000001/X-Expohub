"""
AI 原生层路由（P5 新增，前缀 /api/ai）

- POST /api/ai/generate   {capability, prompt} → 网关生成（脱敏→调用→记账→预算护栏）
- GET  /api/ai/usage/me   我的 AI 用量

预算：settings.AI_MONTHLY_BUDGET_CENTS（默认 100 元/月，0=不限）；
超预算返回 HTTP 429。隐私：prompt 发送前 PII 脱敏，日志不存原文。
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_active_user
from app.core.exceptions import BadRequest
from app.models.base import get_db
from app.models.user import User
from app.modules.ai.llm import gateway, AI_CAPABILITIES
from app.modules.ai.models import AiUsageLog
from app.modules.ai.pii import redact_pii

router = APIRouter(prefix="/ai", tags=["AI 原生"])


class GenerateRequest(BaseModel):
    capability: str = Field("generic", min_length=1, max_length=32)
    prompt: str = Field(..., min_length=1, max_length=4000)


def _month_usage(db: Session) -> int:
    """本月已用费用（分）"""
    now = datetime.now(timezone.utc)
    logs = db.query(AiUsageLog).filter(
        AiUsageLog.created_at >= datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    ).all()
    return sum(l.cost_cents for l in logs)


@router.post("/generate")
def ai_generate(
    data: GenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """调用 AI 能力：脱敏 → 生成 → 记账 → 预算护栏"""
    if data.capability not in AI_CAPABILITIES:
        raise BadRequest(message=f"不支持的能力: {data.capability}，可选: {sorted(AI_CAPABILITIES)}")

    # 预算预检（考虑本次估算后仍不超）
    budget = settings.AI_MONTHLY_BUDGET_CENTS
    used = _month_usage(db)
    if budget > 0 and used >= budget:
        raise BadRequest(message=f"本月 AI 预算已用尽（{used} 分 ≥ 上限 {budget} 分）")

    # 1) PII 脱敏后再外发（不落库原文）
    safe_prompt = redact_pii(data.prompt)

    # 2) 网关调用（fail-soft）
    result = gateway.complete(safe_prompt, data.capability)

    # 3) 记账（mock 不计费；真实渠道按字符单价估算，1 分起）
    cost = 0
    if not result["degraded"]:
        cost = max(1, int(round(len(safe_prompt) / 1000 * settings.AI_COST_PER_1K_CHARS_CENTS)))
    log = AiUsageLog(
        tenant_id=settings.TENANT_DEFAULT,
        capability=data.capability,
        provider=result["provider"],
        user_id=user.id,
        degraded=1 if result["degraded"] else 0,
        prompt_chars=len(safe_prompt),
        response_chars=len(result["content"]),
        cost_cents=cost,
    )
    db.add(log)
    db.commit()

    # 4) 护栏后检（并发窗口内可能略超，仅告警不阻断）
    month_used = _month_usage(db)
    return {"success": True, "code": "OK", "message": "生成成功", "data": {
        "provider": result["provider"],
        "degraded": result["degraded"],
        "content": result["content"],
        "usage": {"cost_cents": cost, "month_cost_cents": month_used,
                  "budget_cents": budget, "budget_unlimited": budget == 0},
    }}


@router.get("/usage/me")
def my_ai_usage(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """我的 AI 用量记录（最近 50 条，不含原文）"""
    logs = db.query(AiUsageLog).filter(AiUsageLog.user_id == user.id) \
        .order_by(AiUsageLog.id.desc()).limit(50).all()
    total_cost = sum(l.cost_cents for l in logs)
    return {"success": True, "code": "OK", "message": "获取成功", "data": {
        "total_cost_cents": total_cost,
        "list": [
            {"id": l.id, "capability": l.capability, "provider": l.provider,
             "degraded": bool(l.degraded), "prompt_chars": l.prompt_chars,
             "response_chars": l.response_chars, "cost_cents": l.cost_cents,
             "created_at": l.created_at.isoformat() if l.created_at else None}
            for l in logs
        ],
    }}
