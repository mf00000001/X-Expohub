"""SQLAlchemy 数据模型 — MOBA 核心表"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship

from src.database import Base


class Hero(Base):
    """英雄"""
    __tablename__ = "heroes"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    name          = Column(String(64), nullable=False, unique=True)
    hp            = Column(Float, nullable=False, default=500)
    mp            = Column(Float, nullable=False, default=300)
    attack_damage = Column(Float, nullable=False, default=60)
    ability_power = Column(Float, nullable=False, default=0)
    armor         = Column(Float, nullable=False, default=30)
    magic_resist  = Column(Float, nullable=False, default=30)
    move_speed    = Column(Float, nullable=False, default=340)
    attack_speed  = Column(Float, nullable=False, default=0.65)
    attack_range  = Column(Float, nullable=False, default=125)

    # 关联技能
    skills = relationship("Skill", back_populates="hero", lazy="selectin")

    def __repr__(self):
        return f"<Hero id={self.id} name={self.name}>"


class Skill(Base):
    """技能"""
    __tablename__ = "skills"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    hero_id         = Column(Integer, ForeignKey("heroes.id"), nullable=False)
    name            = Column(String(64), nullable=False)
    slot            = Column(String(1), nullable=False)               # Q / W / E / R
    damage_base     = Column(Float, nullable=False, default=0)
    damage_ratio_ad = Column(Float, nullable=False, default=0.0)      # 攻击力加成系数
    damage_ratio_ap = Column(Float, nullable=False, default=0.0)      # 法强加成系数
    cooldown        = Column(Float, nullable=False, default=5.0)      # 冷却(秒)
    mana_cost       = Column(Float, nullable=False, default=30)
    cast_range      = Column(Float, nullable=False, default=600)
    description     = Column(Text, nullable=True, default="")

    hero = relationship("Hero", back_populates="skills")

    def __repr__(self):
        return f"<Skill {self.slot} — {self.name}>"


class Item(Base):
    """物品装备"""
    __tablename__ = "items"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    name                = Column(String(64), nullable=False, unique=True)
    price               = Column(Integer, nullable=False)
    sell_price          = Column(Integer, nullable=False)
    category            = Column(String(32), nullable=False)           # Attack / Magic / Defense / Boots
    attributes          = Column(JSON, nullable=False, default=dict)   # {"ad": 40, "ap": 0, "hp": 200, ...}
    passive_description = Column(Text, nullable=True, default="")
    recipe              = Column(JSON, nullable=True, default=None)    # 合成所需物品 ID 列表

    def __repr__(self):
        return f"<Item id={self.id} name={self.name}>"


class Buff(Base):
    """增益效果 (红蓝Buff / 男爵Buff 等)"""
    __tablename__ = "buffs"

    id       = Column(Integer, primary_key=True, autoincrement=True)
    name     = Column(String(64), nullable=False)
    price    = Column(Integer, nullable=False, default=0)
    duration = Column(Float, nullable=False, default=120.0)            # 持续秒数
    effects  = Column(JSON, nullable=False, default=dict)              # {"ad": 20, "ap": 30, ...}

    def __repr__(self):
        return f"<Buff id={self.id} name={self.name}>"


class Match(Base):
    """比赛记录"""
    __tablename__ = "matches"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    start_time  = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time    = Column(DateTime, nullable=True)
    winner_team = Column(Integer, nullable=True)                       # 0 = 蓝方, 1 = 红方

    # 关联
    players = relationship("PlayerMatch", back_populates="match", lazy="selectin")

    def __repr__(self):
        return f"<Match id={self.id} winner={self.winner_team}>"


class PlayerMatch(Base):
    """玩家比赛数据"""
    __tablename__ = "player_matches"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    match_id     = Column(Integer, ForeignKey("matches.id"), nullable=False)
    hero_id      = Column(Integer, ForeignKey("heroes.id"), nullable=False)
    kills        = Column(Integer, nullable=False, default=0)
    deaths       = Column(Integer, nullable=False, default=0)
    assists      = Column(Integer, nullable=False, default=0)
    gold_earned  = Column(Integer, nullable=False, default=0)
    damage_dealt = Column(Float, nullable=False, default=0.0)

    match = relationship("Match", back_populates="players")
    hero  = relationship("Hero")

    def __repr__(self):
        return f"<PlayerMatch match={self.match_id} hero={self.hero_id} KDA={self.kills}/{self.deaths}/{self.assists}>"
