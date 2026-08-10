"""Pydantic 请求/响应 Schema"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ──────────────────── Hero ────────────────────

class SkillOut(BaseModel):
    id: int
    name: str
    slot: str
    damage_base: float
    damage_ratio_ad: float
    damage_ratio_ap: float
    cooldown: float
    mana_cost: float
    cast_range: float
    description: str

    model_config = {"from_attributes": True}


class HeroOut(BaseModel):
    id: int
    name: str
    hp: float
    mp: float
    attack_damage: float
    ability_power: float
    armor: float
    magic_resist: float
    move_speed: float
    attack_speed: float
    attack_range: float

    model_config = {"from_attributes": True}


class HeroDetailOut(HeroOut):
    skills: list[SkillOut] = []


# ──────────────────── Item ────────────────────

class ItemOut(BaseModel):
    id: int
    name: str
    price: int
    sell_price: int
    category: str
    attributes: dict
    passive_description: Optional[str] = ""
    recipe: Optional[list] = None

    model_config = {"from_attributes": True}


# ──────────────────── Buff ────────────────────

class BuffOut(BaseModel):
    id: int
    name: str
    price: int
    duration: float
    effects: dict

    model_config = {"from_attributes": True}


# ──────────────────── Match ────────────────────

class PlayerMatchOut(BaseModel):
    id: int
    match_id: int
    hero_id: int
    kills: int
    deaths: int
    assists: int
    gold_earned: int
    damage_dealt: float

    model_config = {"from_attributes": True}


class MatchOut(BaseModel):
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    winner_team: Optional[int] = None
    players: list[PlayerMatchOut] = []

    model_config = {"from_attributes": True}


# ──────────────────── Simulation ────────────────────

class DamageSimRequest(BaseModel):
    """伤害模拟请求"""
    attacker_ad: float = Field(..., ge=0, description="攻击者攻击力")
    attacker_ap: float = Field(0.0, ge=0, description="攻击者法术强度")
    skill_base_damage: float = Field(..., ge=0, description="技能基础伤害")
    skill_ratio_ad: float = Field(0.0, ge=0, description="技能 AD 加成系数")
    skill_ratio_ap: float = Field(0.0, ge=0, description="技能 AP 加成系数")
    target_armor: float = Field(..., ge=0, description="目标护甲")
    target_magic_resist: float = Field(..., ge=0, description="目标魔抗")
    damage_type: str = Field("physical", description="伤害类型: physical / magic / true")


class DamageSimResponse(BaseModel):
    raw_damage: float
    mitigated_damage: float
    final_damage: float
    damage_type: str


class GoldSimRequest(BaseModel):
    """金币收益模拟请求"""
    minion_kills: int = Field(0, ge=0, description="小兵击杀数")
    hero_kills: int = Field(0, ge=0, description="英雄击杀数")
    assists: int = Field(0, ge=0, description="助攻数")


class GoldSimResponse(BaseModel):
    minion_gold: int
    hero_gold: int
    assist_gold: int
    total_gold: int


class ExperienceRequest(BaseModel):
    """经验值模拟请求"""
    minion_kills: int = Field(0, ge=0)
    hero_kills: int = Field(0, ge=0)
    assists: int = Field(0, ge=0)


class ExperienceResponse(BaseModel):
    minion_exp: int
    hero_exp: int
    assist_exp: int
    total_exp: int


class ItemStackRequest(BaseModel):
    """装备属性叠加请求"""
    item_ids: list[int] = Field(..., description="装备 ID 列表")


class ItemStackResponse(BaseModel):
    items: list[ItemOut]
    total_attributes: dict  # 叠加后的总属性
