// ============================================================
// Map.ts — 三路地图系统
// ============================================================

export interface Obstacle {
    x: number;
    y: number;
    w: number;
    h: number;
    radius?: number;
    isCircle?: boolean;
}

export interface Bush {
    x: number;
    y: number;
    w: number;
    h: number;
}

export interface TowerSpot {
    x: number;
    y: number;
    team: 'blue' | 'red';
    tier: 1 | 2 | 3; // 外塔/内塔/高地塔
}

export const MAP_WIDTH = 2560;
export const MAP_HEIGHT = 1600;

export class GameMap {
    public readonly width = MAP_WIDTH;
    public readonly height = MAP_HEIGHT;

    public obstacles: Obstacle[] = [];
    public bushes: Bush[] = [];
    public towerSpots: TowerSpot[] = [];
    public minionPaths: Array<Array<{ x: number; y: number }>> = [];

    // 河道位置
    public readonly riverY = MAP_HEIGHT / 2;

    constructor() {
        this.generateTerrain();
        this.generateTowerSpots();
        this.generateMinionPaths();
    }

    private generateTerrain(): void {
        const W = this.width;
        const H = this.height;

        // === 地图边界（不可行走）===
        this.obstacles.push(
            { x: -60, y: -60, w: W + 120, h: 60 },       // 顶边
            { x: -60, y: H, w: W + 120, h: 60 },          // 底边
            { x: -60, y: -60, w: 60, h: H + 120 },        // 左边
            { x: W, y: -60, w: 60, h: H + 120 },          // 右边
        );

        const laneCenterY = H / 2;
        const topLaneY = 280;
        const midLaneY = laneCenterY;
        const botLaneY = H - 280;

        // === 上路墙壁 ===
        this.obstacles.push(
            { x: 0, y: topLaneY - 100, w: 300, h: 40 },
            { x: 450, y: topLaneY - 180, w: 350, h: 40 },
            { x: 1000, y: topLaneY - 140, w: 400, h: 40 },
            { x: 1600, y: topLaneY - 200, w: 350, h: 40 },
            { x: 2100, y: topLaneY - 120, w: 460, h: 40 },
        );

        // === 中路墙壁 ===
        this.obstacles.push(
            { x: 0, y: midLaneY - 140, w: 350, h: 40 },
            { x: 500, y: midLaneY - 200, w: 300, h: 40 },
            { x: 1000, y: midLaneY - 160, w: 560, h: 40 },
            { x: 1700, y: midLaneY - 220, w: 300, h: 40 },
            { x: 2150, y: midLaneY - 150, w: 410, h: 40 },
        );

        // === 下路墙壁 ===
        this.obstacles.push(
            { x: 0, y: botLaneY + 60, w: 300, h: 40 },
            { x: 450, y: botLaneY + 140, w: 350, h: 40 },
            { x: 1000, y: botLaneY + 100, w: 400, h: 40 },
            { x: 1600, y: botLaneY + 160, w: 350, h: 40 },
            { x: 2100, y: botLaneY + 80, w: 460, h: 40 },
        );

        // === 野区障碍物 ===
        const jungleRocks: Array<{ x: number; y: number; r: number }> = [
            // 蓝方野区
            { x: 600, y: 500, r: 45 },
            { x: 800, y: 380, r: 50 },
            { x: 550, y: 700, r: 40 },
            { x: 350, y: 600, r: 42 },
            { x: 700, y: 550, r: 35 },
            { x: 900, y: 650, r: 38 },

            // 红方野区
            { x: 1900, y: 500, r: 45 },
            { x: 1750, y: 380, r: 50 },
            { x: 2000, y: 700, r: 40 },
            { x: 2200, y: 600, r: 42 },
            { x: 1850, y: 550, r: 35 },
            { x: 1650, y: 650, r: 38 },

            // 蓝方下野区
            { x: 600, y: 1050, r: 45 },
            { x: 800, y: 1180, r: 50 },
            { x: 550, y: 900, r: 40 },
            { x: 350, y: 1000, r: 42 },

            // 红方下野区
            { x: 1900, y: 1050, r: 45 },
            { x: 1750, y: 1180, r: 50 },
            { x: 2000, y: 900, r: 40 },
            { x: 2200, y: 1000, r: 42 },
        ];

        for (const rock of jungleRocks) {
            this.obstacles.push({
                x: rock.x,
                y: rock.y,
                w: 0,
                h: 0,
                radius: rock.r,
                isCircle: true,
            });
        }

        // === 河道草丛 ===
        this.bushes.push(
            { x: 700, y: laneCenterY - 50, w: 160, h: 100 },
            { x: 1100, y: laneCenterY - 60, w: 200, h: 120 },
            { x: 1500, y: laneCenterY - 50, w: 160, h: 100 },
        );

        // 野区草丛
        this.bushes.push(
            { x: 300, y: 400, w: 100, h: 80 },
            { x: 500, y: 350, w: 90, h: 70 },
            { x: 2100, y: 400, w: 100, h: 80 },
            { x: 1900, y: 350, w: 90, h: 70 },
            { x: 300, y: 1150, w: 100, h: 80 },
            { x: 500, y: 1200, w: 90, h: 70 },
            { x: 2100, y: 1150, w: 100, h: 80 },
            { x: 1900, y: 1200, w: 90, h: 70 },
        );
    }

    private generateTowerSpots(): void {
        const W = this.width;
        const H = this.height;
        const topY = 280;
        const midY = H / 2;
        const botY = H - 280;

        // 蓝方塔
        this.towerSpots.push(
            { x: 180, y: topY, team: 'blue', tier: 1 },
            { x: 480, y: topY, team: 'blue', tier: 2 },
            { x: 780, y: topY, team: 'blue', tier: 3 },

            { x: 200, y: midY, team: 'blue', tier: 1 },
            { x: 550, y: midY, team: 'blue', tier: 2 },
            { x: 900, y: midY, team: 'blue', tier: 3 },

            { x: 180, y: botY, team: 'blue', tier: 1 },
            { x: 480, y: botY, team: 'blue', tier: 2 },
            { x: 780, y: botY, team: 'blue', tier: 3 },
        );

        // 红方塔
        this.towerSpots.push(
            { x: W - 180, y: topY, team: 'red', tier: 1 },
            { x: W - 480, y: topY, team: 'red', tier: 2 },
            { x: W - 780, y: topY, team: 'red', tier: 3 },

            { x: W - 200, y: midY, team: 'red', tier: 1 },
            { x: W - 550, y: midY, team: 'red', tier: 2 },
            { x: W - 900, y: midY, team: 'red', tier: 3 },

            { x: W - 180, y: botY, team: 'red', tier: 1 },
            { x: W - 480, y: botY, team: 'red', tier: 2 },
            { x: W - 780, y: botY, team: 'red', tier: 3 },
        );
    }

    private generateMinionPaths(): void {
        const W = this.width;
        const H = this.height;
        const topY = 280;
        const midY = H / 2;
        const botY = H - 280;

        // 小兵行进路线（简化：直线路径点）
        const topPath: Array<{ x: number; y: number }> = [
            { x: -50, y: topY },
            { x: 180, y: topY },
            { x: 480, y: topY },
            { x: 780, y: topY },
            { x: 1280, y: topY },
            { x: W - 780, y: topY },
            { x: W - 480, y: topY },
            { x: W - 180, y: topY },
            { x: W + 50, y: topY },
        ];

        const midPath: Array<{ x: number; y: number }> = [
            { x: -50, y: midY },
            { x: 200, y: midY },
            { x: 550, y: midY },
            { x: 900, y: midY },
            { x: 1280, y: midY },
            { x: W - 900, y: midY },
            { x: W - 550, y: midY },
            { x: W - 200, y: midY },
            { x: W + 50, y: midY },
        ];

        const botPath: Array<{ x: number; y: number }> = [
            { x: -50, y: botY },
            { x: 180, y: botY },
            { x: 480, y: botY },
            { x: 780, y: botY },
            { x: 1280, y: botY },
            { x: W - 780, y: botY },
            { x: W - 480, y: botY },
            { x: W - 180, y: botY },
            { x: W + 50, y: botY },
        ];

        this.minionPaths = [topPath, midPath, botPath];
    }

    /** 获取所有障碍物（供寻路使用） */
    public getObstaclesForPathfinding(): Obstacle[] {
        return this.obstacles;
    }

    /** 获取草丛列表 */
    public getBushes(): Bush[] {
        return this.bushes;
    }

    /** 检查某点是否在草丛中 */
    public isInBush(wx: number, wy: number): boolean {
        for (const bush of this.bushes) {
            if (wx >= bush.x && wx <= bush.x + bush.w && wy >= bush.y && wy <= bush.y + bush.h) {
                return true;
            }
        }
        return false;
    }
}
