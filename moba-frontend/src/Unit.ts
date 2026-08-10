// ============================================================
// Unit.ts — 单位基类
// ============================================================

import { Point } from './Pathfinding.js';

export type Team = 'blue' | 'red' | 'neutral';

export interface UnitStats {
    maxHP: number;
    hp: number;
    maxMP: number;
    mp: number;
    attackDamage: number;
    attackSpeed: number;   // 每秒攻击次数
    attackRange: number;
    armor: number;
    magicResist: number;
    moveSpeed: number;     // 像素/秒
    hpRegen: number;       // 每秒恢复
    mpRegen: number;
}

export abstract class Unit {
    public x: number;
    public y: number;
    public radius: number = 18;
    public team: Team;
    public stats: UnitStats;

    // 移动
    public path: Point[] = [];
    public pathIndex: number = 0;
    public targetMoveX: number = 0;
    public targetMoveY: number = 0;
    public isMoving: boolean = false;

    // 攻击
    public attackTarget: Unit | null = null;
    public attackCooldown: number = 0;
    public isAttacking: boolean = false;
    public attackAnimTimer: number = 0;

    // 状态
    public isAlive: boolean = true;
    public isInBush: boolean = false;

    // 经验/等级（英雄用）
    public level: number = 1;
    public xp: number = 0;
    public xpToLevel: number = 100;

    // 金币
    public goldValue: number = 0;

    // 可见性
    public visible: boolean = true;

    constructor(x: number, y: number, team: Team, stats: UnitStats) {
        this.x = x;
        this.y = y;
        this.team = team;
        this.stats = { ...stats };
    }

    /** 设置移动目标路径 */
    public setPath(path: Point[]): void {
        if (path.length === 0) return;
        this.path = path;
        this.pathIndex = 0;
        this.isMoving = true;
        this.attackTarget = null;
    }

    /** 设置攻击目标 */
    public setAttackTarget(target: Unit): void {
        this.attackTarget = target;
        this.isMoving = false;
        this.path = [];
    }

    /** 每帧更新 */
    public update(deltaTime: number): void {
        if (!this.isAlive) return;

        // 恢复
        this.stats.hp = Math.min(this.stats.maxHP, this.stats.hp + this.stats.hpRegen * deltaTime);
        this.stats.mp = Math.min(this.stats.maxMP, this.stats.mp + this.stats.mpRegen * deltaTime);

        // 攻击冷却
        if (this.attackCooldown > 0) {
            this.attackCooldown -= deltaTime;
        }

        // 攻击动画
        if (this.attackAnimTimer > 0) {
            this.attackAnimTimer -= deltaTime;
            if (this.attackAnimTimer <= 0) {
                this.isAttacking = false;
            }
        }

        // 如果有攻击目标
        if (this.attackTarget) {
            if (!this.attackTarget.isAlive) {
                this.attackTarget = null;
            } else {
                const dist = this.distanceTo(this.attackTarget);
                if (dist <= this.stats.attackRange) {
                    // 在攻击范围内
                    this.isMoving = false;
                    if (this.attackCooldown <= 0) {
                        this.performAttack(this.attackTarget);
                    }
                } else {
                    // 不在范围内，需要靠近
                    this.moveToward(this.attackTarget.x, this.attackTarget.y, deltaTime);
                }
            }
            return;
        }

        // 沿路径移动
        if (this.isMoving && this.path.length > 0 && this.pathIndex < this.path.length) {
            const target = this.path[this.pathIndex];
            const dx = target.x - this.x;
            const dy = target.y - this.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < 4) {
                this.pathIndex++;
                if (this.pathIndex >= this.path.length) {
                    this.isMoving = false;
                    this.path = [];
                }
            } else {
                const speed = this.stats.moveSpeed * deltaTime;
                if (speed >= dist) {
                    this.x = target.x;
                    this.y = target.y;
                    this.pathIndex++;
                    if (this.pathIndex >= this.path.length) {
                        this.isMoving = false;
                        this.path = [];
                    }
                } else {
                    this.x += (dx / dist) * speed;
                    this.y += (dy / dist) * speed;
                }
            }
        } else if (this.pathIndex >= this.path.length) {
            this.isMoving = false;
        }
    }

    /** 向某点移动 */
    private moveToward(tx: number, ty: number, deltaTime: number): void {
        const dx = tx - this.x;
        const dy = ty - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 2) return;
        const speed = this.stats.moveSpeed * deltaTime;
        this.x += (dx / dist) * Math.min(speed, dist);
        this.y += (dy / dist) * Math.min(speed, dist);
    }

    /** 执行攻击 */
    public performAttack(target: Unit): void {
        this.attackCooldown = 1.0 / this.stats.attackSpeed;
        this.isAttacking = true;
        this.attackAnimTimer = 0.25;
        // 伤害由 CombatSystem 处理
    }

    /** 受到伤害 */
    public takeDamage(physicalDamage: number, magicDamage: number = 0): number {
        if (!this.isAlive) return 0;

        const physReduction = this.stats.armor / (this.stats.armor + 100);
        const magReduction = this.stats.magicResist / (this.stats.magicResist + 100);

        const totalDamage = physicalDamage * (1 - physReduction) + magicDamage * (1 - magReduction);
        const actualDamage = Math.max(1, Math.round(totalDamage));

        this.stats.hp -= actualDamage;
        if (this.stats.hp <= 0) {
            this.stats.hp = 0;
            this.isAlive = false;
            this.onDeath();
        }
        return actualDamage;
    }

    /** 死亡回调 */
    protected onDeath(): void {
        this.isAlive = false;
        this.isMoving = false;
        this.path = [];
        this.attackTarget = null;
    }

    /** 到另一个单位的距离 */
    public distanceTo(other: Unit): number {
        return Math.hypot(this.x - other.x, this.y - other.y);
    }

    /** 到某点的距离 */
    public distanceToPoint(px: number, py: number): number {
        return Math.hypot(this.x - px, this.y - py);
    }

    /** 面向角度 */
    public facingAngle(): number {
        if (this.attackTarget) {
            return Math.atan2(this.attackTarget.y - this.y, this.attackTarget.x - this.x);
        }
        if (this.isMoving && this.path.length > 0 && this.pathIndex < this.path.length) {
            const t = this.path[this.pathIndex];
            return Math.atan2(t.y - this.y, t.x - this.x);
        }
        return 0;
    }

    /** 获取 HP 百分比 */
    public getHPPercent(): number {
        return this.stats.hp / this.stats.maxHP;
    }

    /** 获取 MP 百分比 */
    public getMPPercent(): number {
        return this.stats.mp / this.stats.maxMP;
    }
}
