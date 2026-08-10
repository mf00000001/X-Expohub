// ============================================================
// SkillSystem.ts — 技能系统
// ============================================================

import { Hero } from './Hero.js';
import { Unit } from './Unit.js';

export type SkillType = 'targeted' | 'self' | 'direction' | 'aoe';

export interface SkillData {
    name: string;
    key: string;            // Q / W / E / R
    icon: string;           // emoji
    cooldown: number;       // 冷却时间（秒）
    currentCooldown: number;
    manaCost: number;
    range: number;
    damageMultiplier: number;
    description: string;
    type: SkillType;
}

export class Skill {
    public slot: number;    // 0=Q, 1=W, 2=E, 3=R
    public data: SkillData;

    constructor(slot: number, data: SkillData) {
        this.slot = slot;
        this.data = { ...data };
    }

    /** 每帧更新冷却 */
    public update(deltaTime: number): void {
        if (this.data.currentCooldown > 0) {
            this.data.currentCooldown = Math.max(0, this.data.currentCooldown - deltaTime);
        }
    }

    /** 检查是否可以施放 */
    public canCast(hero: Hero): string | null {
        if (!hero.isAlive) return '已死亡';
        if (this.data.currentCooldown > 0) return '技能冷却中';
        if (hero.stats.mp < this.data.manaCost) return '法力不足';
        return null; // 可以施法
    }

    /** 开始冷却 */
    public startCooldown(): void {
        this.data.currentCooldown = this.data.cooldown;
    }

    /** 冷却进度 (0~1, 1=冷却完毕) */
    public getCooldownPercent(): number {
        if (this.data.cooldown <= 0) return 1;
        return 1 - this.data.currentCooldown / this.data.cooldown;
    }

    /** 冷却剩余秒数 */
    public getCooldownRemaining(): number {
        return Math.ceil(this.data.currentCooldown);
    }

    /** 获取技能原始伤害（施放者攻击力 × 伤害系数） */
    public getRawDamage(hero: Hero): number {
        return hero.stats.attackDamage * this.data.damageMultiplier;
    }

    /** 获取技能键名 */
    public getKey(): string {
        return this.data.key;
    }
}
