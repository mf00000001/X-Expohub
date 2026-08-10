"""REST API 路由"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models import Hero, Skill, Item, Buff, Match, PlayerMatch
from src.schemas import (
    HeroOut, HeroDetailOut, SkillOut,
    ItemOut, BuffOut,
    MatchOut, PlayerMatchOut,
    DamageSimRequest, DamageSimResponse,
    GoldSimRequest, GoldSimResponse,
    ExperienceRequest, ExperienceResponse,
    ItemStackRequest, ItemStackResponse,
)
from src.game_logic import (
    calculate_damage,
    calculate_gold,
    calculate_experience,
    stack_item_attributes,
)

router = APIRouter(prefix="/api", tags=["MOBA API"])


# ──────────────────── Hero ────────────────────

@router.get("/heroes", response_model=list[HeroOut])
async def list_heroes(db: AsyncSession = Depends(get_db)):
    """获取全部英雄列表"""
    result = await db.execute(select(Hero))
    return result.scalars().all()


@router.get("/heroes/{hero_id}", response_model=HeroDetailOut)
async def get_hero(hero_id: int, db: AsyncSession = Depends(get_db)):
    """获取英雄详情（含技能）"""
    result = await db.execute(
        select(Hero).where(Hero.id == hero_id).options(selectinload(Hero.skills))
    )
    hero = result.scalar_one_or_none()
    if not hero:
        raise HTTPException(status_code=404, detail="英雄不存在")
    return hero


@router.get("/heroes/{hero_id}/skills", response_model=list[SkillOut])
async def get_hero_skills(hero_id: int, db: AsyncSession = Depends(get_db)):
    """获取某英雄的全部技能"""
    result = await db.execute(select(Skill).where(Skill.hero_id == hero_id))
    return result.scalars().all()


# ──────────────────── Item ────────────────────

@router.get("/items", response_model=list[ItemOut])
async def list_items(
    category: str = Query(None, description="按分类筛选: Attack / Magic / Defense / Boots"),
    db: AsyncSession = Depends(get_db),
):
    """获取装备列表，可按分类筛选"""
    stmt = select(Item)
    if category:
        stmt = stmt.where(Item.category == category)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/items/{item_id}", response_model=ItemOut)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个装备详情"""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    return item


# ──────────────────── Buff ────────────────────

@router.get("/buffs", response_model=list[BuffOut])
async def list_buffs(db: AsyncSession = Depends(get_db)):
    """获取所有 Buff 列表"""
    result = await db.execute(select(Buff))
    return result.scalars().all()


# ──────────────────── Simulation: Damage ────────────────────

@router.post("/simulate/damage", response_model=DamageSimResponse)
async def simulate_damage(body: DamageSimRequest):
    """
    伤害模拟计算。
    支持 physical / magic / true 三种伤害类型。
    """
    result = calculate_damage(
        attacker_ad=body.attacker_ad,
        attacker_ap=body.attacker_ap,
        skill_base_damage=body.skill_base_damage,
        skill_ratio_ad=body.skill_ratio_ad,
        skill_ratio_ap=body.skill_ratio_ap,
        target_armor=body.target_armor,
        target_magic_resist=body.target_magic_resist,
        damage_type=body.damage_type,
    )
    return DamageSimResponse(**result)


# ──────────────────── Simulation: Gold ────────────────────

@router.post("/simulate/gold", response_model=GoldSimResponse)
async def simulate_gold(body: GoldSimRequest):
    """金币收益计算：小兵 20g / 英雄 300g / 助攻 150g"""
    result = calculate_gold(
        minion_kills=body.minion_kills,
        hero_kills=body.hero_kills,
        assists=body.assists,
    )
    return GoldSimResponse(**result)


# ──────────────────── Simulation: Experience ────────────────────

@router.post("/simulate/experience", response_model=ExperienceResponse)
async def simulate_experience(body: ExperienceRequest):
    """经验值计算"""
    result = calculate_experience(
        minion_kills=body.minion_kills,
        hero_kills=body.hero_kills,
        assists=body.assists,
    )
    return ExperienceResponse(**result)


# ──────────────────── Simulation: Item Stack ────────────────────

@router.post("/simulate/item-stack", response_model=ItemStackResponse)
async def simulate_item_stack(body: ItemStackRequest, db: AsyncSession = Depends(get_db)):
    """
    装备属性叠加计算。
    传入装备 ID 列表，返回每件装备详情 + 叠加后的总属性。
    """
    result = await db.execute(select(Item).where(Item.id.in_(body.item_ids)))
    items = result.scalars().all()

    if len(items) != len(body.item_ids):
        found_ids = {i.id for i in items}
        missing = set(body.item_ids) - found_ids
        raise HTTPException(status_code=404, detail=f"装备不存在: {missing}")

    total = stack_item_attributes(items)
    return ItemStackResponse(
        items=[ItemOut.model_validate(i) for i in items],
        total_attributes=total,
    )


# ──────────────────── Match ────────────────────

@router.get("/matches", response_model=list[MatchOut])
async def list_matches(db: AsyncSession = Depends(get_db)):
    """获取比赛记录列表"""
    result = await db.execute(
        select(Match).options(selectinload(Match.players))
    )
    return result.scalars().all()


@router.get("/matches/{match_id}", response_model=MatchOut)
async def get_match(match_id: int, db: AsyncSession = Depends(get_db)):
    """获取单场比赛详情（含玩家数据）"""
    result = await db.execute(
        select(Match)
        .where(Match.id == match_id)
        .options(selectinload(Match.players))
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="比赛不存在")
    return match
