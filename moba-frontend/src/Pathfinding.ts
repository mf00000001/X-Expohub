// ============================================================
// Pathfinding.ts — A* 寻路系统
// ============================================================

export interface GridNode {
    x: number;
    y: number;
    g: number;      // 起点到当前的成本
    h: number;      // 启发式估算
    f: number;      // g + h
    parent: GridNode | null;
    walkable: boolean;
}

export interface Point {
    x: number;
    y: number;
}

export class Pathfinding {
    private grid: GridNode[][] = [];
    private gridWidth: number = 0;
    private gridHeight: number = 0;
    private cellSize: number;

    // 地图世界坐标偏移
    private offsetX: number = 0;
    private offsetY: number = 0;

    // 障碍物集合（世界坐标）
    private obstacles: Array<{ x: number; y: number; w: number; h: number; radius?: number; isCircle?: boolean }> = [];

    constructor(cellSize: number = 40) {
        this.cellSize = cellSize;
    }

    /** 根据世界边界初始化网格 */
    public initialize(worldWidth: number, worldHeight: number, offsetX: number = 0, offsetY: number = 0): void {
        this.offsetX = offsetX;
        this.offsetY = offsetY;
        this.gridWidth = Math.ceil(worldWidth / this.cellSize) + 1;
        this.gridHeight = Math.ceil(worldHeight / this.cellSize) + 1;

        this.grid = [];
        for (let y = 0; y < this.gridHeight; y++) {
            this.grid[y] = [];
            for (let x = 0; x < this.gridWidth; x++) {
                this.grid[y][x] = {
                    x,
                    y,
                    g: 0,
                    h: 0,
                    f: 0,
                    parent: null,
                    walkable: true,
                };
            }
        }
    }

    /** 设置障碍物列表 */
    public setObstacles(obstacles: Array<{ x: number; y: number; w: number; h: number; radius?: number; isCircle?: boolean }>): void {
        this.obstacles = obstacles;
        this.refreshWalkability();
    }

    /** 刷新所有格子的可通过性 */
    private refreshWalkability(): void {
        for (let y = 0; y < this.gridHeight; y++) {
            for (let x = 0; x < this.gridWidth; x++) {
                const wx = this.gridToWorldX(x);
                const wy = this.gridToWorldY(y);
                this.grid[y][x].walkable = !this.isBlocked(wx, wy);
            }
        }
    }

    /** 检查世界坐标是否被障碍物阻挡 */
    private isBlocked(wx: number, wy: number): boolean {
        const halfCell = this.cellSize / 2;
        for (const obs of this.obstacles) {
            if (obs.isCircle && obs.radius !== undefined) {
                const dx = wx - obs.x;
                const dy = wy - obs.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < obs.radius + halfCell) return true;
            } else {
                // 矩形碰撞
                const margin = halfCell * 0.8;
                if (
                    wx + margin > obs.x &&
                    wx - margin < obs.x + obs.w &&
                    wy + margin > obs.y &&
                    wy - margin < obs.y + obs.h
                ) {
                    return true;
                }
            }
        }
        return false;
    }

    /** 世界坐标 → 网格坐标 */
    public worldToGrid(wx: number, wy: number): { gx: number; gy: number } {
        return {
            gx: Math.floor((wx - this.offsetX) / this.cellSize),
            gy: Math.floor((wy - this.offsetY) / this.cellSize),
        };
    }

    private gridToWorldX(gx: number): number {
        return gx * this.cellSize + this.cellSize / 2 + this.offsetX;
    }

    private gridToWorldY(gy: number): number {
        return gy * this.cellSize + this.cellSize / 2 + this.offsetY;
    }

    /** 获取格子中心世界坐标 */
    public gridCenterToWorld(gx: number, gy: number): Point {
        return {
            x: gx * this.cellSize + this.cellSize / 2 + this.offsetX,
            y: gy * this.cellSize + this.cellSize / 2 + this.offsetY,
        };
    }

    /** 检查格子在网格范围内 */
    private inBounds(gx: number, gy: number): boolean {
        return gx >= 0 && gx < this.gridWidth && gy >= 0 && gy < this.gridHeight;
    }

    /** 曼哈顿距离 */
    private manhattan(a: Point, b: Point): number {
        return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
    }

    /** 八方向距离 (Octile) */
    private octile(a: Point, b: Point): number {
        const dx = Math.abs(a.x - b.x);
        const dy = Math.abs(a.y - b.y);
        return Math.max(dx, dy) + (Math.SQRT2 - 1) * Math.min(dx, dy);
    }

    /** A* 寻路主函数 */
    public findPath(startWX: number, startWY: number, endWX: number, endWY: number): Point[] {
        const start = this.worldToGrid(startWX, startWY);
        const end = this.worldToGrid(endWX, endWY);

        // 如果起点或终点超出范围
        if (!this.inBounds(start.gx, start.gy) || !this.inBounds(end.gx, end.gy)) {
            return [{ x: endWX, y: endWY }];
        }

        // 如果终点不可行走，尝试找最近可行走点
        if (!this.grid[end.gy][end.gx].walkable) {
            const nearest = this.findNearestWalkable(end.gx, end.gy);
            if (!nearest) return [{ x: endWX, y: endWY }];
            return this.findPath(startWX, startWY,
                this.gridCenterToWorld(nearest.x, nearest.y).x,
                this.gridCenterToWorld(nearest.x, nearest.y).y
            );
        }

        // 重置所有节点
        for (let y = 0; y < this.gridHeight; y++) {
            for (let x = 0; x < this.gridWidth; x++) {
                this.grid[y][x].g = Infinity;
                this.grid[y][x].h = 0;
                this.grid[y][x].f = Infinity;
                this.grid[y][x].parent = null;
            }
        }

        const openList: GridNode[] = [];
        const closedSet = new Set<string>();

        const startNode = this.grid[start.gy][start.gx];
        startNode.g = 0;
        const endPt: Point = { x: end.gx, y: end.gy };
        const startPt: Point = { x: start.gx, y: start.gy };
        startNode.h = this.octile(startPt, endPt);
        startNode.f = startNode.h;
        openList.push(startNode);

        // 8方向邻居
        const dirs = [
            { dx: 0, dy: -1 }, { dx: 1, dy: -1 }, { dx: 1, dy: 0 }, { dx: 1, dy: 1 },
            { dx: 0, dy: 1 }, { dx: -1, dy: 1 }, { dx: -1, dy: 0 }, { dx: -1, dy: -1 },
        ];

        const key = (x: number, y: number) => `${x},${y}`;

        while (openList.length > 0) {
            // 找最小 f 值
            let bestIdx = 0;
            for (let i = 1; i < openList.length; i++) {
                if (openList[i].f < openList[bestIdx].f) bestIdx = i;
            }

            const current = openList[bestIdx];
            openList.splice(bestIdx, 1);

            // 到达终点
            if (current.x === end.gx && current.y === end.gy) {
                return this.reconstructPath(current);
            }

            closedSet.add(key(current.x, current.y));

            for (const dir of dirs) {
                const nx = current.x + dir.dx;
                const ny = current.y + dir.dy;

                if (!this.inBounds(nx, ny)) continue;
                if (closedSet.has(key(nx, ny))) continue;

                const neighbor = this.grid[ny][nx];
                if (!neighbor.walkable) {
                    closedSet.add(key(nx, ny));
                    continue;
                }

                // 对角线移动时检查两侧是否通畅
                if (dir.dx !== 0 && dir.dy !== 0) {
                    if (!this.grid[current.y][nx].walkable || !this.grid[ny][current.x].walkable) {
                        continue;
                    }
                }

                const moveCost = (dir.dx !== 0 && dir.dy !== 0) ? Math.SQRT2 : 1;
                const tentativeG = current.g + moveCost;

                if (tentativeG < neighbor.g) {
                    neighbor.g = tentativeG;
                    neighbor.h = this.octile({ x: nx, y: ny }, endPt);
                    neighbor.f = neighbor.g + neighbor.h;
                    neighbor.parent = current;

                    // 如果不在开放列表中则加入
                    let inOpen = false;
                    for (const n of openList) {
                        if (n.x === nx && n.y === ny) { inOpen = true; break; }
                    }
                    if (!inOpen) {
                        openList.push(neighbor);
                    }
                }
            }
        }

        // 无路径，返回最近可行走点
        const nearest = this.findNearestWalkable(start.gx, start.gy);
        if (nearest) {
            return [this.gridCenterToWorld(nearest.x, nearest.y)];
        }
        return [{ x: endWX, y: endWY }];
    }

    /** 重建路径 */
    private reconstructPath(endNode: GridNode): Point[] {
        const path: Point[] = [];
        let current: GridNode | null = endNode;
        while (current) {
            path.push(this.gridCenterToWorld(current.x, current.y));
            current = current.parent;
        }
        path.reverse();
        return this.smoothPath(path);
    }

    /** 路径平滑（拉绳法） */
    private smoothPath(path: Point[]): Point[] {
        if (path.length <= 2) return path;

        const smoothed: Point[] = [path[0]];
        let currentIdx = 0;

        while (currentIdx < path.length - 1) {
            let furthest = currentIdx + 1;
            for (let i = path.length - 1; i > currentIdx; i--) {
                if (this.lineOfSight(path[currentIdx], path[i])) {
                    furthest = i;
                    break;
                }
            }
            smoothed.push(path[furthest]);
            currentIdx = furthest;
        }

        return smoothed;
    }

    /** 两点间是否有视线 */
    private lineOfSight(a: Point, b: Point): boolean {
        const steps = Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / (this.cellSize * 0.5));
        for (let i = 0; i <= steps; i++) {
            const t = i / steps;
            const wx = a.x + (b.x - a.x) * t;
            const wy = a.y + (b.y - a.y) * t;
            if (this.isBlocked(wx, wy)) return false;
        }
        return true;
    }

    /** 找最近可行走格子 */
    private findNearestWalkable(gx: number, gy: number): { x: number; y: number } | null {
        for (let r = 1; r < 20; r++) {
            for (let dy = -r; dy <= r; dy++) {
                for (let dx = -r; dx <= r; dx++) {
                    const nx = gx + dx;
                    const ny = gy + dy;
                    if (this.inBounds(nx, ny) && this.grid[ny][nx].walkable) {
                        return { x: nx, y: ny };
                    }
                }
            }
        }
        return null;
    }

    /** 获取路径节点数（用于调试） */
    public getGridInfo(): { width: number; height: number; cellSize: number } {
        return { width: this.gridWidth, height: this.gridHeight, cellSize: this.cellSize };
    }
}
