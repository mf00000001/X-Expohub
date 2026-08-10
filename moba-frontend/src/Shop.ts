// ============================================================
// Shop.ts — 商店系统
// ============================================================

import { Hero, Equipment } from './Hero.js';

export class Shop {
    public isOpen: boolean = false;
    public items: Equipment[];

    private panelEl: HTMLElement;
    private itemsContainerEl: HTMLElement;

    constructor(panelEl: HTMLElement, itemsContainerEl: HTMLElement) {
        this.panelEl = panelEl;
        this.itemsContainerEl = itemsContainerEl;
        this.items = this.createItemList();
        this.renderItems();
    }

    /** 创建装备列表 */
    private createItemList(): Equipment[] {
        return [
            {
                name: '多兰之剑',
                icon: '🗡️',
                cost: 450,
                hpBonus: 80,
                mpBonus: 0,
                adBonus: 8,
                asBonus: 0,
                armorBonus: 0,
                mrBonus: 0,
                msBonus: 0,
                description: '+8 AD  +80 HP  +2.5% 生命偷取',
            },
            {
                name: '多兰之戒',
                icon: '💍',
                cost: 400,
                hpBonus: 70,
                mpBonus: 0,
                adBonus: 0,
                asBonus: 0,
                armorBonus: 0,
                mrBonus: 0,
                msBonus: 0,
                description: '+15 AP  +70 HP  +50% 回蓝',
            },
            {
                name: '长剑',
                icon: '🔪',
                cost: 350,
                hpBonus: 0,
                mpBonus: 0,
                adBonus: 10,
                asBonus: 0,
                armorBonus: 0,
                mrBonus: 0,
                msBonus: 0,
                description: '+10 攻击力',
            },
            {
                name: '增幅典籍',
                icon: '📖',
                cost: 435,
                hpBonus: 0,
                mpBonus: 0,
                adBonus: 0,
                asBonus: 0,
                armorBonus: 0,
                mrBonus: 0,
                msBonus: 0,
                description: '+20 法术强度',
            },
            {
                name: '狂战士胫甲',
                icon: '👢',
                cost: 1100,
                hpBonus: 0,
                mpBonus: 0,
                adBonus: 0,
                asBonus: 35,
                armorBonus: 0,
                mrBonus: 0,
                msBonus: 45,
                description: '+35% 攻速  +45 移速',
            },
            {
                name: '无尽之刃',
                icon: '⚔️',
                cost: 3400,
                hpBonus: 0,
                mpBonus: 0,
                adBonus: 70,
                asBonus: 0,
                armorBonus: 0,
                mrBonus: 0,
                msBonus: 0,
                description: '+70 AD  +20% 暴击 暴击伤害225%',
            },
            {
                name: '破败王者之刃',
                icon: '🏹',
                cost: 3200,
                hpBonus: 0,
                mpBonus: 0,
                adBonus: 40,
                asBonus: 25,
                armorBonus: 0,
                mrBonus: 0,
                msBonus: 0,
                description: '+40 AD  +25% 攻速  +10% 吸血',
            },
            {
                name: '日炎斗篷',
                icon: '🛡️',
                cost: 2800,
                hpBonus: 500,
                mpBonus: 0,
                adBonus: 0,
                asBonus: 0,
                armorBonus: 50,
                mrBonus: 0,
                msBonus: 0,
                description: '+500 HP  +50 护甲  灼烧光环',
            },
            {
                name: '荆棘之甲',
                icon: '🦔',
                cost: 2700,
                hpBonus: 350,
                mpBonus: 0,
                adBonus: 0,
                asBonus: 0,
                armorBonus: 70,
                mrBonus: 0,
                msBonus: 0,
                description: '+350 HP  +70 护甲  反伤',
            },
            {
                name: '振奋盔甲',
                icon: '💠',
                cost: 2900,
                hpBonus: 450,
                mpBonus: 0,
                adBonus: 0,
                asBonus: 0,
                armorBonus: 25,
                mrBonus: 50,
                msBonus: 0,
                description: '+450 HP  +25 护甲  +50 魔抗',
            },
        ];
    }

    /** 渲染商店物品列表 */
    private renderItems(): void {
        this.itemsContainerEl.innerHTML = this.items
            .map(
                (item, index) => `
                <div class="shop-item" data-index="${index}">
                    <div>
                        <span class="shop-item-name">${item.icon} ${item.name}</span>
                        <div class="shop-item-desc">${item.description}</div>
                    </div>
                    <span class="shop-item-cost">🪙 ${item.cost}</span>
                </div>
            `
            )
            .join('');

        // 绑定点击事件
        const itemEls = this.itemsContainerEl.querySelectorAll('.shop-item');
        itemEls.forEach((el) => {
            el.addEventListener('click', (e) => {
                const index = parseInt((el as HTMLElement).dataset.index || '0');
                this.onItemClick(index);
            });
        });
    }

    /** 购买回调（由外部设置） */
    public onBuyCallback: ((item: Equipment) => boolean) | null = null;

    private onItemClick(index: number): void {
        const item = this.items[index];
        if (!item) return;

        if (this.onBuyCallback) {
            const success = this.onBuyCallback(item);
            if (!success) {
                this.showMessage('金币不足或装备栏已满！', '#e74c3c');
            } else {
                this.showMessage(`购买成功：${item.name}`, '#2ecc71');
            }
        }
    }

    /** 显示临时消息 */
    private showMessage(text: string, color: string): void {
        const msg = document.createElement('div');
        msg.textContent = text;
        msg.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: ${color};
            font-size: 18px;
            font-weight: bold;
            text-shadow: 0 0 8px #000;
            pointer-events: none;
            z-index: 999;
            animation: fadeOut 1.5s forwards;
        `;
        document.body.appendChild(msg);
        setTimeout(() => msg.remove(), 1500);
    }

    /** 尝试购买 */
    public tryBuy(hero: Hero, item: Equipment): boolean {
        if (hero.gold < item.cost) return false;
        if (!hero.canEquip()) return false;

        hero.spendGold(item.cost);
        hero.addEquipment(item);
        return true;
    }

    /** 切换商店面板 */
    public toggle(): void {
        this.isOpen = !this.isOpen;
        if (this.isOpen) {
            this.panelEl.classList.add('open');
        } else {
            this.panelEl.classList.remove('open');
        }
    }

    /** 关闭商店 */
    public close(): void {
        this.isOpen = false;
        this.panelEl.classList.remove('open');
    }
}
