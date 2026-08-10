"""
MOBA 核心游戏逻辑 — 纯 Python 计算引擎
─────────────────────────────────────────
包含：伤害公式、技能伤害、金币/经验计算、装备叠加
"""

from src.models import Hero, Skill, Item, Buff


# ──────────────────── 常量 ────────────────────
GOLD_MINION = 20       # 小兵击杀金币
GOLD_HERO   = 300      # 英雄击杀金币
GOLD_ASSIST = 150      # 助攻金币

EXP_MINION  = 60       # 小兵经验
EXP_HERO    = 300      # 英雄击杀经验
EXP_ASSIST  = 150      # 助攻经验


# ──────────────────── 伤害计算 ────────────────────

def calculate_physical_damage(raw_damage: float, armor: float) -> float:
    """
    物理伤害减免公式：
        final_damage = raw_damage * (100 / (100 + armor))
    """
    if armor < 0:
        # 负护甲时伤害加深
        return raw_damage * (2 - 100 / (100 - armor))
    return raw_damage * (100.0 / (100.0 + armor))


def calculate_magic_damage(raw_damage: float, magic_resist: float) -> float:
    """
    魔法伤害减免公式（与物理相同，使用魔抗）：
        final_damage = raw_damage * (100 / (100 + magic_resist))
    """
    if magic_resist < 0:
        return raw_damage * (2 - 100 / (100 - magic_resist))
    return raw_damage * (100.0 / (100.0 + magic_resist))


def calculate_damage(
    attacker_ad: float,
    attacker_ap: float,
    skill_base_damage: float,
    skill_ratio_ad: float,
    skill_ratio_ap: float,
    target_armor: float,
    target_magic_resist: float,
    damage_type: str = "physical",
) -> dict:
    """
    完整伤害计算。

    参数
    ----
    attacker_ad        : 攻击者攻击力
    attacker_ap        : 攻击者法术强度
    skill_base_damage  : 技能基础伤害
    skill_ratio_ad     : 技能 AD 加成系数
    skill_ratio_ap     : 技能 AP 加成系数
    target_armor       : 目标护甲
    target_magic_resist: 目标魔抗
    damage_type        : physical / magic / true

    返回
    ----
    {
        "raw_damage"      : 减免前伤害,
        "mitigated_damage": 被减免的伤害,
        "final_damage"    : 最终伤害,
        "damage_type"     : 伤害类型
    }
    """
    # 1. 计算原始伤害 = 技能基础伤害 + AD加成 + AP加成
    raw = skill_base_damage + (attacker_ad * skill_ratio_ad) + (attacker_ap * skill_ratio_ap)

    # 2. 根据伤害类型减免
    if damage_type == "true":
        final = raw
    elif damage_type == "magic":
        final = calculate_magic_damage(raw, target_magic_resist)
    else:  # physical (default)
        final = calculate_physical_damage(raw, target_armor)

    return {
        "raw_damage":       round(raw, 2),
        "mitigated_damage": round(raw - final, 2),
        "final_damage":     round(final, 2),
        "damage_type":      damage_type,
    }


def simulate_skill_damage(
    hero: Hero,
    skill: Skill,
    target_armor: float = 30,
    target_magic_resist: float = 30,
    bonus_ad: float = 0,
    bonus_ap: float = 0,
    damage_type: str = "physical",
) -> dict:
    """
    根据英雄+技能模拟伤害。
    """
    total_ad = hero.attack_damage + bonus_ad
    total_ap = hero.ability_power + bonus_ap

    return calculate_damage(
        attacker_ad=total_ad,
        attacker_ap=total_ap,
        skill_base_damage=skill.damage_base,
        skill_ratio_ad=skill.damage_ratio_ad,
        skill_ratio_ap=skill.damage_ratio_ap,
        target_armor=target_armor,
        target_magic_resist=target_magic_resist,
        damage_type=damage_type,
    )


# ──────────────────── 金币 & 经验 ────────────────────

def calculate_gold(
    minion_kills: int = 0,
    hero_kills: int = 0,
    assists: int = 0,
) -> dict:
    """
    计算金币收益。
    """
    mg = minion_kills * GOLD_MINION
    hg = hero_kills * GOLD_HERO
    ag = assists * GOLD_ASSIST
    return {
        "minion_gold": mg,
        "hero_gold":   hg,
        "assist_gold": ag,
        "total_gold":  mg + hg + ag,
    }


def calculate_experience(
    minion_kills: int = 0,
    hero_kills: int = 0,
    assists: int = 0,
) -> dict:
    """
    计算经验值。
    """
    me = minion_kills * EXP_MINION
    he = hero_kills * EXP_HERO
    ae = assists * EXP_ASSIST
    return {
        "minion_exp": me,
        "hero_exp":   he,
        "assist_exp": ae,
        "total_exp":  me + he + ae,
    }


# ──────────────────── 装备属性叠加 ────────────────────

def stack_item_attributes(items: list[Item]) -> dict:
    """
    叠加多个装备的属性。

    装备 attributes 示例:
        {"ad": 40, "hp": 200, "armor": 25}
    多个装备的同名属性直接相加。
    """
    total: dict = {}
    for item in items:
        for key, value in item.attributes.items():
            total[key] = total.get(key, 0) + value
    return total


def simulate_full_combat(
    hero: Hero,
    skill: Skill,
    items: list[Item],
    buffs: list[Buff],
    target_armor: float,
    target_magic_resist: float,
    damage_type: str = "physical",
) -> dict:
    """
    全状态模拟：英雄 + 技能 + 装备 + Buff → 对目标造成的伤害。
    """
    # 叠加装备属性
    item_stats = stack_item_attributes(items) if items else {}

    # 叠加 Buff 属性
    buff_stats: dict = {}
    for b in (buffs or []):
        for k, v in b.effects.items():
            buff_stats[k] = buff_stats.get(k, 0) + v

    # 合并额外属性
    bonus_ad = item_stats.get("ad", 0) + buff_stats.get("ad", 0)
    bonus_ap = item_stats.get("ap", 0) + buff_stats.get("ap", 0)

    total_ad = hero.attack_damage + bonus_ad
    total_ap = hero.ability_power + bonus_ap

    result = calculate_damage(
        attacker_ad=total_ad,
        attacker_ap=total_ap,
        skill_base_damage=skill.damage_base,
        skill_ratio_ad=skill.damage_ratio_ad,
        skill_ratio_ap=skill.damage_ratio_ap,
        target_armor=target_armor,
        target_magic_resist=target_magic_resist,
        damage_type=damage_type,
    )
    result["bonus_ad"] = round(bonus_ad, 2)
    result["bonus_ap"] = round(bonus_ap, 2)
    result["item_stats"] = item_stats
    result["buff_stats"] = buff_stats
    return result
