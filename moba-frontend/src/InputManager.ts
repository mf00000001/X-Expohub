// ============================================================
// InputManager.ts — 输入管理器
// ============================================================

export enum MouseButton {
    Left = 0,
    Middle = 1,
    Right = 2,
}

export interface InputState {
    mouseX: number;
    mouseY: number;
    worldMouseX: number;
    worldMouseY: number;
    leftClick: boolean;
    rightClick: boolean;
    leftHold: boolean;
    rightHold: boolean;
    keysDown: Set<string>;
    keysJustPressed: Set<string>;
}

export class InputManager {
    private canvas: HTMLCanvasElement;
    private state: InputState;
    private prevKeysDown: Set<string> = new Set();

    // 相机偏移（用于世界坐标转换）
    public cameraX: number = 0;
    public cameraY: number = 0;

    // 回调
    public onRightClick: ((wx: number, wy: number) => void) | null = null;
    public onLeftClick: ((wx: number, wy: number) => void) | null = null;
    public onSkillKey: ((slot: number) => void) | null = null;
    public onShopToggle: (() => void) | null = null;

    constructor(canvas: HTMLCanvasElement) {
        this.canvas = canvas;

        this.state = {
            mouseX: 0,
            mouseY: 0,
            worldMouseX: 0,
            worldMouseY: 0,
            leftClick: false,
            rightClick: false,
            leftHold: false,
            rightHold: false,
            keysDown: new Set(),
            keysJustPressed: new Set(),
        };

        this.setupListeners();
    }

    private setupListeners(): void {
        const rect = this.canvas.getBoundingClientRect();

        // 鼠标移动
        this.canvas.addEventListener('mousemove', (e: MouseEvent) => {
            const r = this.canvas.getBoundingClientRect();
            const scaleX = this.canvas.width / r.width;
            const scaleY = this.canvas.height / r.height;
            this.state.mouseX = (e.clientX - r.left) * scaleX;
            this.state.mouseY = (e.clientY - r.top) * scaleY;
            this.state.worldMouseX = this.state.mouseX + this.cameraX;
            this.state.worldMouseY = this.state.mouseY + this.cameraY;
        });

        // 鼠标按下
        this.canvas.addEventListener('mousedown', (e: MouseEvent) => {
            e.preventDefault();
            const r = this.canvas.getBoundingClientRect();
            const scaleX = this.canvas.width / r.width;
            const scaleY = this.canvas.height / r.height;
            const mx = (e.clientX - r.left) * scaleX;
            const my = (e.clientY - r.top) * scaleY;
            const wx = mx + this.cameraX;
            const wy = my + this.cameraY;

            this.state.mouseX = mx;
            this.state.mouseY = my;
            this.state.worldMouseX = wx;
            this.state.worldMouseY = wy;

            if (e.button === MouseButton.Right) {
                this.state.rightClick = true;
                this.state.rightHold = true;
                this.onRightClick?.(wx, wy);
            }
            if (e.button === MouseButton.Left) {
                this.state.leftClick = true;
                this.state.leftHold = true;
                this.onLeftClick?.(wx, wy);
            }
        });

        // 鼠标释放
        window.addEventListener('mouseup', (e: MouseEvent) => {
            if (e.button === MouseButton.Left) {
                this.state.leftHold = false;
            }
            if (e.button === MouseButton.Right) {
                this.state.rightHold = false;
            }
        });

        // 键盘按下
        window.addEventListener('keydown', (e: KeyboardEvent) => {
            const key = e.key.toLowerCase();
            if (!this.state.keysDown.has(key)) {
                this.state.keysJustPressed.add(key);
            }
            this.state.keysDown.add(key);

            // 技能快捷键
            if (key === 'q') this.onSkillKey?.(0);
            if (key === 'w') this.onSkillKey?.(1);
            if (key === 'e') this.onSkillKey?.(2);
            if (key === 'r') this.onSkillKey?.(3);

            // 商店
            if (key === 'p') this.onShopToggle?.();

            e.preventDefault();
        });

        // 键盘释放
        window.addEventListener('keyup', (e: KeyboardEvent) => {
            this.state.keysDown.delete(e.key.toLowerCase());
        });

        // 阻止右键菜单
        this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
    }

    /** 每帧结束时调用，清除瞬时状态 */
    public endFrame(): void {
        this.state.leftClick = false;
        this.state.rightClick = false;
        this.state.keysJustPressed.clear();
    }

    public getState(): InputState {
        return this.state;
    }

    public isKeyDown(key: string): boolean {
        return this.state.keysDown.has(key);
    }

    public isKeyJustPressed(key: string): boolean {
        return this.state.keysJustPressed.has(key);
    }
}
