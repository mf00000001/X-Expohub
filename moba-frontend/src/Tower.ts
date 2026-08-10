// ============================================================
// Tower.ts — 防御塔类
// ============================================================

import { Unit, UnitStats, Team } from './Unit.js';

export class Tower extends Unit {
    public tier: 1 | 2 | 3;        // 外塔/内塔/高地塔
    public isDestroyed: boolean = false;

    private searchRange: number = 450;   // 攻击范围（大于英雄）
    private towerAttackCD: number = 0;
    private readonly towerAttackRate: number = 0.8;  // 每秒攻击 0.8 次

    constructor(x: number, y: number, team: Team, tier: 1 | 2 | 3) {
        const hpByTier = tier === 3 ? 3000 : tier === 2 ? 2500 : 2000;
        const adByTier = tier === 3 ? 200 : tier === 2 ? 170 : 150;

        const stats: UnitStats = {
            maxHP: hpByTier,
            hp: hpByTier,
            maxMP: 0,
            mp: 0,
            attackDamage: adByTier,
            attackSpeed: 0.8,
            attackRange: 450,
            armor: 60,
            magicResist: 40,
            moveSpeed: 0,         // 防御塔不能移动
            hpRegen: 0,
            mpRegen: 0,
        };

        super(x, y, team, stats);
        this.radius = 30;
        this.tier = tier;
        this.goldValue = tier === 3 ? 200 : tier === 2 ? 150 : 100;
    }

    public update(deltaTime: number, allUnits?: Unit[]): void {
        if (!this.isAlive || this.isDestroyed) return;

        // 攻击冷却
        if (this.towerAttackCD > 0) {
            this.towerAttackCD -= deltaTime;
        }

        // 搜索目标
        if (allUnits && this.towerAttackCD <= 0) {
            const target = this.findTarget(allUnits);
            if (target) {
                this.attackTarget = target;
                this.towerAttackCD = 1.0 / this.towerAttackRate;
                this.performAttack(target);
            }
        }

        // 清除死亡目标
        if (this.attackTarget && !this.attackTarget.isAlive) {
            this.attackTarget = null;
        }

        super.update(deltaTime);
    }

    /** 搜索攻击目标：优先小兵，其次英雄 */
    private findTarget(units: Unit[]): Unit | null {
        let closestMinion: Unit | null = null;
        let closestMinionDist = this.searchRange;
        let closestHero: Unit | null = null;
        let closestHeroDist = this.searchRange;

        for (const u of units) {
            if (!u.isAlive || u === this) continue;
            if (u.team === this.team) continue;  // 不攻击同队

            const dist = this.distanceTo(u);
            if (dist > this.searchRange) continue;

            // 判断是否为英雄（检查 goldValue 区分）
            if (u.goldValue >= 200) {
                // 英雄
                if (dist < closestHeroDist) {
                    closestHeroDist = dist;
                    closestHero = u;
                }
            } else {
                // 小兵
                if (dist < closestMinionDist) {
                    closestMinionDist = dist;
                    closestMinion = u;
                }
            }
        }

        // 优先攻击小兵（塔下保护机制）
        return closestMinion || closestHero;
    }

    protected onDeath(): void {
        super.onDeath();
        this.isDestroyed = true;
        this.isAlive = false;
    }
}
