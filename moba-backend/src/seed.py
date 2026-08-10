"""
种子数据脚本 — 填充示例英雄、技能、装备、Buff
运行方式: python -m src.seed
"""

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_factory, init_db
from src.models import Hero, Skill, Item, Buff


HEROES_DATA = [
    {
        "name": "亚瑟", "hp": 600, "mp": 0, "attack_damage": 65,
        "ability_power": 0, "armor": 40, "magic_resist": 32,
        "move_speed": 345, "attack_speed": 0.65, "attack_range": 125,
        "skills": [
            {"name": "沉默打击", "slot": "Q", "damage_base": 80, "damage_ratio_ad": 1.0,
             "damage_ratio_ap": 0.0, "cooldown": 8, "mana_cost": 0, "cast_range": 300,
             "description": "对目标造成物理伤害并沉默1.5秒"},
            {"name": "勇气之盾", "slot": "W", "damage_base": 0, "damage_ratio_ad": 0.0,
             "damage_ratio_ap": 0.0, "cooldown": 12, "mana_cost": 0, "cast_range": 0,
             "description": "获得护盾，吸收伤害"},
            {"name": "回旋打击", "slot": "E", "damage_base": 120, "damage_ratio_ad": 0.6,
             "damage_ratio_ap": 0.0, "cooldown": 10, "mana_cost": 0, "cast_range": 400,
             "description": "旋转攻击周围敌人"},
            {"name": "圣剑裁决", "slot": "R", "damage_base": 300, "damage_ratio_ad": 1.5,
             "damage_ratio_ap": 0.0, "cooldown": 60, "mana_cost": 0, "cast_range": 500,
             "description": "召唤圣剑对目标造成巨额真实伤害"},
        ]
    },
    {
        "name": "艾希", "hp": 480, "mp": 280, "attack_damage": 58,
        "ability_power": 0, "armor": 25, "magic_resist": 28,
        "move_speed": 325, "attack_speed": 0.72, "attack_range": 600,
        "skills": [
            {"name": "冰霜射击", "slot": "Q", "damage_base": 40, "damage_ratio_ad": 1.1,
             "damage_ratio_ap": 0.0, "cooldown": 4, "mana_cost": 40, "cast_range": 600,
             "description": "射出冰箭，减速目标"},
            {"name": "万箭齐发", "slot": "W", "damage_base": 100, "damage_ratio_ad": 1.0,
             "damage_ratio_ap": 0.0, "cooldown": 8, "mana_cost": 60, "cast_range": 800,
             "description": "向前方扇形区域射出多支箭矢"},
            {"name": "鹰击长空", "slot": "E", "damage_base": 0, "damage_ratio_ad": 0.0,
             "damage_ratio_ap": 0.0, "cooldown": 30, "mana_cost": 0, "cast_range": 3000,
             "description": "派出猎鹰侦查地图区域"},
            {"name": "魔法水晶箭", "slot": "R", "damage_base": 250, "damage_ratio_ad": 1.2,
             "damage_ratio_ap": 0.5, "cooldown": 90, "mana_cost": 100, "cast_range": 2500,
             "description": "发射巨大冰箭，眩晕第一个命中的敌方英雄"},
        ]
    },
    {
        "name": "安妮", "hp": 460, "mp": 400, "attack_damage": 48,
        "ability_power": 25, "armor": 22, "magic_resist": 30,
        "move_speed": 330, "attack_speed": 0.6, "attack_range": 575,
        "skills": [
            {"name": "火球术", "slot": "Q", "damage_base": 90, "damage_ratio_ad": 0.0,
             "damage_ratio_ap": 0.8, "cooldown": 3, "mana_cost": 50, "cast_range": 600,
             "description": "投掷火球造成魔法伤害"},
            {"name": "焚烧", "slot": "W", "damage_base": 120, "damage_ratio_ad": 0.0,
             "damage_ratio_ap": 0.85, "cooldown": 7, "mana_cost": 70, "cast_range": 500,
             "description": "锥形区域造成魔法伤害"},
            {"name": "熔岩护盾", "slot": "E", "damage_base": 0, "damage_ratio_ad": 0.0,
             "damage_ratio_ap": 0.0, "cooldown": 12, "mana_cost": 40, "cast_range": 400,
             "description": "给自己或友军提供护盾"},
            {"name": "提伯斯之怒", "slot": "R", "damage_base": 350, "damage_ratio_ad": 0.0,
             "damage_ratio_ap": 1.0, "cooldown": 100, "mana_cost": 125, "cast_range": 600,
             "description": "召唤巨熊提伯斯，造成范围魔法伤害"},
        ]
    },
]

ITEMS_DATA = [
    {
        "name": "无尽之刃", "price": 3400, "sell_price": 2380, "category": "Attack",
        "attributes": {"ad": 70, "critical_chance": 0.20},
        "passive_description": "暴击伤害提升至225%",
        "recipe": [1038, 1037, 1018],
    },
    {
        "name": "破败王者之刃", "price": 3200, "sell_price": 2240, "category": "Attack",
        "attributes": {"ad": 40, "attack_speed": 0.25, "life_steal": 0.10},
        "passive_description": "攻击命中造成目标当前生命值6%的额外物理伤害",
        "recipe": [1053, 1036, 1042],
    },
    {
        "name": "灭世者的死亡之帽", "price": 3600, "sell_price": 2520, "category": "Magic",
        "attributes": {"ap": 120},
        "passive_description": "法术强度提升35%",
        "recipe": [1058, 1058],
    },
    {
        "name": "卢登的回声", "price": 3200, "sell_price": 2240, "category": "Magic",
        "attributes": {"ap": 90, "mana": 600, "ability_haste": 20},
        "passive_description": "技能命中时造成额外溅射魔法伤害",
        "recipe": [1058, 1026],
    },
    {
        "name": "日炎斗篷", "price": 2800, "sell_price": 1960, "category": "Defense",
        "attributes": {"hp": 500, "armor": 50},
        "passive_description": "每秒对周围敌人造成魔法伤害",
        "recipe": [1031, 1028],
    },
    {
        "name": "荆棘之甲", "price": 2700, "sell_price": 1890, "category": "Defense",
        "attributes": {"hp": 350, "armor": 70},
        "passive_description": "受到普通攻击时反弹魔法伤害",
        "recipe": [1031, 1029],
    },
    {
        "name": "狂战士胫甲", "price": 1100, "sell_price": 770, "category": "Boots",
        "attributes": {"attack_speed": 0.35, "move_speed": 45},
        "passive_description": "",
        "recipe": [1001, 1042],
    },
    {
        "name": "法师之靴", "price": 1100, "sell_price": 770, "category": "Boots",
        "attributes": {"magic_penetration": 18, "move_speed": 45},
        "passive_description": "",
        "recipe": [1001],
    },
    {
        "name": "多兰之剑", "price": 450, "sell_price": 180, "category": "Attack",
        "attributes": {"ad": 8, "hp": 80, "life_steal": 0.025},
        "passive_description": "",
        "recipe": None,
    },
    {
        "name": "多兰之戒", "price": 400, "sell_price": 160, "category": "Magic",
        "attributes": {"ap": 15, "hp": 70, "mana_regen": 0.5},
        "passive_description": "",
        "recipe": None,
    },
]

BUFFS_DATA = [
    {
        "name": "红Buff", "price": 0, "duration": 120,
        "effects": {"ad": 15, "slow_on_hit": 0.10, "burn_damage": 20},
    },
    {
        "name": "蓝Buff", "price": 0, "duration": 120,
        "effects": {"ap": 25, "mana_regen": 1.0, "ability_haste": 20},
    },
    {
        "name": "男爵Buff", "price": 0, "duration": 180,
        "effects": {"ad": 40, "ap": 40, "minion_boost": 1},
    },
    {
        "name": "愤怒合剂", "price": 500, "duration": 180,
        "effects": {"ad": 30, "life_steal": 0.12},
    },
    {
        "name": "巫术合剂", "price": 500, "duration": 180,
        "effects": {"ap": 50, "mana_regen": 0.75},
    },
]


async def seed():
    """填充种子数据"""
    await init_db()

    async with async_session_factory() as session:
        # 检查是否已有数据
        existing = (await session.execute(select(Hero))).scalars().first()
        if existing:
            print("⚠️  数据库已有数据，跳过种子填充。")
            return

        # ── 英雄 + 技能 ──
        for hd in HEROES_DATA:
            skills_data = hd.pop("skills")
            hero = Hero(**hd)
            session.add(hero)
            await session.flush()  # 获得 hero.id

            for sd in skills_data:
                skill = Skill(hero_id=hero.id, **sd)
                session.add(skill)

        # ── 装备 ──
        for id_ in ITEMS_DATA:
            item = Item(**id_)
            session.add(item)

        # ── Buff ──
        for bd in BUFFS_DATA:
            buff = Buff(**bd)
            session.add(buff)

        await session.commit()
        print("✅ 种子数据填充完成！")
        print(f"   - {len(HEROES_DATA)} 个英雄 + 技能")
        print(f"   - {len(ITEMS_DATA)} 件装备")
        print(f"   - {len(BUFFS_DATA)} 个 Buff")


if __name__ == "__main__":
    asyncio.run(seed())
