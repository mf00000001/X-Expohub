// ============================================================
// Minion.ts — 小兵类
// ============================================================

import { Unit, UnitStats, Team } from './Unit.js';
import { Point } from './Pathfinding.js';

export type LaneType = 'top' | 'mid' | 'bot';

export class Minion extends Unit {
    public lane: LaneType;
    public lanePath: Point[];
    public pathWaypointIndex: number = 0;
    public direction: 1 | -1; // 1 = 向敌方基地方向（红方小兵向左），-1 = 向蓝方
    public aggroRange: number = 300;
    public autoAttackRange: number = 100;

    // 自动攻击计时
    private autoAttackCD: number = 0;

    constructor(x: number, y: number, team: Team, lane: LaneType, lanePath: Point[], direction: 1 | -1) {
        const stats: UnitStats = {
            maxHP: 300,
            hp: 300,
            maxMP: 0,
            mp: 0,
            attackDamage: 20,
            attackSpeed: 0.8,
            attackRange: 100,
            armor: 5,
            magicResist: 0,
            moveSpeed: 200,
            hpRegen: 0,
            mpRegen: 0,
        };

        super(x, y, team, stats);
        this.radius = 14;
        this.lane = lane;
        this.lanePath = lanePath;
        this.direction = direction;
        this.goldValue = 25;

        // 初始化路径索引
        this.initPathIndex();
    }

    private initPathIndex(): void {
        if (this.direction === 1) {
            // 从蓝方走向红方（从左到右）
            this.pathWaypointIndex = 0;
            for (let i = 0; i < this.lanePath.length; i++) {
                if (this.lanePath[i].x >= this.x) {
                    this.pathWaypointIndex = i;
                    break;
                }
            }
        } else {
            // 从红方走向蓝方
            this.pathWaypointIndex = this.lanePath.length - 1;
            for (let i = this.lanePath.length - 1; i >= 0; i--) {
                if (this.lanePath[i].x <= this.x) {
                    this.pathWaypointIndex = i;
                    break;
                }
            }
        }
    }

    public update(deltaTime: number, allUnits?: Unit[]): void {
        if (!this.isAlive) return;

        // 自动攻击冷却
        if (this.autoAttackCD > 0) {
            this.autoAttackCD -= deltaTime;
        }

        // 寻找攻击目标
        if (allUnits) {
            const target = this.findTarget(allUnits);
            if (target) {
                this.setAttackTarget(target);
                if (this.autoAttackCD <= 0 && this.distanceTo(target) <= this.autoAttackRange) {
                    this.autoAttackCD = 1.0 / this.stats.attackSpeed;
                    this.performAttack(target);
                }
            }
        }

        // 如果没有攻击目标，沿兵线移动
        if (!this.attackTarget || !this.attackTarget.isAlive) {
            this.attackTarget = null;
            this.moveAlongLane(deltaTime);
        }

        super.update(deltaTime);
    }

    private findTarget(units: Unit[]): Unit | null {
        let closest: Unit | null = null;
        let closestDist = this.aggroRange;

        for (const u of units) {
            if (!u.isAlive || u === this) continue;
            if (u.team === this.team) continue;

            const dist = this.distanceTo(u);
            if (dist < closestDist) {
                // 优先攻击英雄
                if (u instanceof (await import('./Hero.js')).Hero) {
                    closestDist = dist;
                    closest = u;
                    break; // 优先攻击英雄
                }
                if (!closest || dist < closestDist) {
                    closestDist = dist;
                    closest = u;
                }
            }
        }

        return closest;
    }

    private moveAlongLane(deltaTime: number): void {
        if (this.lanePath.length === 0) return;

        const currentWaypoint = this.lanePath[this.pathWaypointIndex];
        const dx = currentWaypoint.x - this.x;
        const dy = currentWaypoint.y - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 8) {
            // 到达当前路径点，移到下一个
            if (this.direction === 1) {
                this.pathWaypointIndex++;
                if (this.pathWaypointIndex >= this.lanePath.length) {
                    this.pathWaypointIndex = this.lanePath.length - 1;
                    this.isAlive = false; // 到达终点，消失
                }
            } else {
                this.pathWaypointIndex--;
                if (this.pathWaypointIndex < 0) {
                    this.pathWaypointIndex = 0;
                    this.isAlive = false;
                }
            }
        } else {
            const speed = this.stats.moveSpeed * deltaTime;
            this.x += (dx / dist) * Math.min(speed, dist);
            this.y += (dy / dist) * Math.min(speed, dist);
        }
    }

    protected onDeath(): void {
        super.onDeath();
    }
}
