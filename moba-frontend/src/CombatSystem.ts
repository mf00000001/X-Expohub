// ============================================================
// CombatSystem.ts — 战斗系统
// ============================================================

import { Unit } from './Unit.js';
import { Hero } from './Hero.js';
import { Skill } from './SkillSystem.js';

export interface CombatEvent {
    type: 'attack' | 'skill' | 'kill' | 'death' | 'gold';
    source?: Unit;
    target?: Unit;
    damage?: number;
    goldEarned?: number;
    skillName?: string;
    message: string;
}

export class CombatSystem {
    public events: CombatEvent[] = [];
    private maxEvents: number = 20;

    constructor() {
        this.events = [];
    }

    /** 处理普通攻击 */
    public processAttack(attacker: Unit, target: Unit): CombatEvent {
        const rawDamage = attacker.stats.attackDamage;
        const actualDamage = target.takeDamage(rawDamage, 0);

        const event: CombatEvent = {
            type: 'attack',
            source: attacker,
            target,
            damage: actualDamage,
            message: `${this.getUnitName(attacker)} 攻击 ${this.getUnitName(target)} 造成 ${actualDamage} 点伤害`,
        };

        this.addEvent(event);

        // 检查击杀
        if (!target.isAlive) {
            this.processKill(attacker, target);
        }

        return event;
    }

    /** 处理技能伤害 */
    public processSkillDamage(caster: Hero, skill: Skill, target: Unit): CombatEvent {
        const rawDamage = skill.getRawDamage(caster);
        const actualDamage = target.takeDamage(rawDamage, 0);

        const event: CombatEvent = {
            type: 'skill',
            source: caster,
            target,
            damage: actualDamage,
            skillName: skill.data.name,
            message: `${this.getUnitName(caster)} 使用 [${skill.data.name}] 对 ${this.getUnitName(target)} 造成 ${actualDamage} 点伤害`,
        };

        this.addEvent(event);

        if (!target.isAlive) {
            this.processKill(caster, target);
        }

        return event;
    }

    /** 处理 AOE 技能伤害 */
    public processAOEDamage(caster: Hero, skill: Skill, targets: Unit[]): CombatEvent[] {
        const events: CombatEvent[] = [];
        for (const target of targets) {
            if (!target.isAlive || target === caster) continue;
            if (target.team === caster.team) continue;

            const event = this.processSkillDamage(caster, skill, target);
            events.push(event);
        }
        return events;
    }

    /** 处理击杀 */
    private processKill(killer: Unit, victim: Unit): void {
        const goldReward = victim.goldValue || 0;

        // 给击杀者金币（如果是 Hero 实例）
        if (killer instanceof Hero && goldReward > 0) {
            killer.addGold(goldReward);
            killer.kills++;
            (killer as Hero).addXP(goldReward >= 200 ? 300 : 60);
        }

        const killEvent: CombatEvent = {
            type: 'kill',
            source: killer,
            target: victim,
            goldEarned: goldReward,
            message: `${this.getUnitName(killer)} 击杀了 ${this.getUnitName(victim)} (+${goldReward}💰)`,
        };
        this.addEvent(killEvent);
    }

    /** 处理死亡（英雄） */
    public processHeroDeath(hero: Hero, killer?: Unit): void {
        if (killer && killer !== hero) {
            // 助攻逻辑（简化：周围友军获得助攻）
        }

        const event: CombatEvent = {
            type: 'death',
            target: hero,
            source: killer,
            message: `${this.getUnitName(hero)} 已被击杀`,
        };
        this.addEvent(event);
    }

    /** 添加事件到队列 */
    private addEvent(event: CombatEvent): void {
        this.events.push(event);
        if (this.events.length > this.maxEvents) {
            this.events.shift();
        }
    }

    /** 获取最近事件 */
    public getRecentEvents(count: number = 5): CombatEvent[] {
        return this.events.slice(-count);
    }

    /** 获取最后一个事件 */
    public getLastEvent(): CombatEvent | null {
        return this.events.length > 0 ? this.events[this.events.length - 1] : null;
    }

    /** 清空事件 */
    public clearEvents(): void {
        this.events = [];
    }

    /** 获取单位名称 */
    private getUnitName(unit: Unit): string {
        if (unit instanceof Hero) {
            return unit.isPlayer ? '你' : '敌方英雄';
        }
        // Minion or Tower
        if (unit.goldValue >= 100) return '防御塔';
        return '小兵';
    }

    /** 计算物理伤害减免 */
    public static getPhysicalReduction(armor: number): number {
        return armor / (armor + 100);
    }

    /** 计算魔法伤害减免 */
    public static getMagicReduction(magicResist: number): number {
        return magicResist / (magicResist + 100);
    }
}
