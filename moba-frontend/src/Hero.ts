// ============================================================
// Hero.ts — 英雄类
// ============================================================

import { Unit, UnitStats, Team } from './Unit.js';
import { Skill, SkillData } from './SkillSystem.js';

export class Hero extends Unit {
    public skills: Skill[] = [];
    public equipment: (Equipment | null)[] = [null, null, null, null, null, null];
    public gold: number = 500;
    public kills: number = 0;
    public deaths: number = 0;
    public assists: number = 0;
    public respawnTimer: number = 0;
    public spawnX: number;
    public spawnY: number;
    public isPlayer: boolean;

    // 基础属性（不含装备加成）
    private baseStats: UnitStats;

    constructor(x: number, y: number, team: Team, isPlayer: boolean = false) {
        const stats: UnitStats = {
            maxHP: 600,
            hp: 600,
            maxMP: 400,
            mp: 400,
            attackDamage: 65,
            attackSpeed: 0.75,
            attackRange: 125,
            armor: 30,
            magicResist: 25,
            moveSpeed: 320,
            hpRegen: 2,
            mpRegen: 1.5,
        };

        super(x, y, team, stats);
        this.radius = 24;
        this.spawnX = x;
        this.spawnY = y;
        this.isPlayer = isPlayer;
        this.baseStats = { ...stats };
        this.goldValue = 300;

        this.initSkills();
    }

    private initSkills(): void {
        const skillData: SkillData[] = [
            {
                name: '斩击',
                key: 'Q',
                icon: '⚔️',
                cooldown: 6,
                currentCooldown: 0,
                manaCost: 40,
                range: 150,
                damageMultiplier: 1.5,
                description: '对前方敌人造成150%攻击力的物理伤害',
                type: 'targeted',
            },
            {
                name: '护盾',
                key: 'W',
                icon: '🛡️',
                cooldown: 12,
                currentCooldown: 0,
                manaCost: 50,
                range: 0,
                damageMultiplier: 0,
                description: '获得一个持续3秒的护盾，吸收100点伤害',
                type: 'self',
            },
            {
                name: '突进',
                key: 'E',
                icon: '💨',
                cooldown: 10,
                currentCooldown: 0,
                manaCost: 60,
                range: 300,
                damageMultiplier: 0.8,
                description: '向鼠标方向突进，对路径敌人造成80%攻击力伤害',
                type: 'direction',
            },
            {
                name: '大招',
                key: 'R',
                icon: '🔥',
                cooldown: 30,
                currentCooldown: 0,
                manaCost: 100,
                range: 250,
                damageMultiplier: 3.0,
                description: '对周围所有敌人造成300%攻击力的AOE伤害',
                type: 'aoe',
            },
        ];

        this.skills = skillData.map((data, i) => new Skill(i, data));
    }

    public update(deltaTime: number): void {
        if (!this.isAlive) {
            this.respawnTimer -= deltaTime;
            if (this.respawnTimer <= 0) {
                this.respawn();
            }
            return;
        }

        super.update(deltaTime);

        // 更新技能冷却
        for (const skill of this.skills) {
            skill.update(deltaTime);
        }
    }

    /** 使用技能 */
    public useSkill(slot: number, targetX?: number, targetY?: number, targetUnit?: Unit): string | null {
        if (!this.isAlive) return '已死亡';
        if (slot < 0 || slot >= this.skills.length) return '无效技能';

        const skill = this.skills[slot];
        const checkResult = skill.canCast(this);
        if (checkResult) return checkResult;

        // 消耗法力
        this.stats.mp -= skill.data.manaCost;
        skill.startCooldown();

        return null; // 成功，效果由外部处理
    }

    /** 获取技能 */
    public getSkill(slot: number): Skill | null {
        if (slot < 0 || slot >= this.skills.length) return null;
        return this.skills[slot];
    }

    /** 获得金币 */
    public addGold(amount: number): void {
        this.gold += amount;
    }

    /** 花费金币 */
    public spendGold(amount: number): boolean {
        if (this.gold >= amount) {
            this.gold -= amount;
            return true;
        }
        return false;
    }

    /** 装备加成属性 */
    public recalcStats(): void {
        // 从基础属性开始
        this.stats = { ...this.baseStats };
        this.stats.hp = Math.min(this.stats.hp, this.stats.maxHP);
        this.stats.mp = Math.min(this.stats.mp, this.stats.maxMP);

        for (const eq of this.equipment) {
            if (eq) {
                this.stats.maxHP += eq.hpBonus;
                this.stats.hp += eq.hpBonus;
                this.stats.maxMP += eq.mpBonus;
                this.stats.mp += eq.mpBonus;
                this.stats.attackDamage += eq.adBonus;
                this.stats.attackSpeed += eq.asBonus;
                this.stats.armor += eq.armorBonus;
                this.stats.magicResist += eq.mrBonus;
                this.stats.moveSpeed += eq.msBonus;
            }
        }
    }

    /** 获得经验 */
    public addXP(amount: number): void {
        this.xp += amount;
        while (this.xp >= this.xpToLevel) {
            this.xp -= this.xpToLevel;
            this.levelUp();
        }
    }

    private levelUp(): void {
        this.level++;
        this.xpToLevel = Math.floor(this.xpToLevel * 1.5);

        // 升级属性提升
        this.baseStats.maxHP += 80;
        this.baseStats.hp = this.baseStats.maxHP;
        this.baseStats.maxMP += 40;
        this.baseStats.mp = this.baseStats.maxMP;
        this.baseStats.attackDamage += 5;
        this.baseStats.attackSpeed += 0.02;
        this.baseStats.armor += 3;
        this.baseStats.magicResist += 2;

        this.recalcStats();
    }

    /** 死亡处理 */
    protected onDeath(): void {
        super.onDeath();
        this.deaths++;
        this.respawnTimer = 5 + this.level * 2; // 秒
    }

    /** 复活 */
    private respawn(): void {
        this.isAlive = true;
        this.x = this.spawnX;
        this.y = this.spawnY;
        this.stats.hp = this.stats.maxHP;
        this.stats.mp = this.stats.maxMP;
        this.respawnTimer = 0;
        this.path = [];
        this.isMoving = false;
        this.attackTarget = null;
        for (const skill of this.skills) {
            skill.data.currentCooldown = 0;
        }
    }

    /** 是否可以购买装备 */
    public canEquip(): boolean {
        return this.equipment.some(slot => slot === null);
    }

    /** 添加装备 */
    public addEquipment(eq: Equipment): boolean {
        for (let i = 0; i < this.equipment.length; i++) {
            if (this.equipment[i] === null) {
                this.equipment[i] = eq;
                this.recalcStats();
                return true;
            }
        }
        return false;
    }
}

// ============================================================
// 装备数据结构
// ============================================================
export interface Equipment {
    name: string;
    icon: string;
    cost: number;
    hpBonus: number;
    mpBonus: number;
    adBonus: number;
    asBonus: number;
    armorBonus: number;
    mrBonus: number;
    msBonus: number;
    description: string;
}
