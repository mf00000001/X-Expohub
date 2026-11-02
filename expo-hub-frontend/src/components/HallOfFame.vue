<script setup lang="ts">
import { computed } from 'vue'
import type { HallOfFameItem } from '@/api/exhibition'

// 全球标杆展会（≤10 场，长期固定在首页展示）。
// 数据由父组件 HomeView 统一请求 GET /exhibitions/hall-of-fame 后传入，
// 顺序即后端给的展示顺序，这里不排序、不补造、不截断成假数据。
//
// 注意：这些是人工精选的静态清单，条目 id 并不在 exhibitions 表里，
// 点开 /exhibitions/:id 必然 404 —— 所以卡片一律不可点击、不做键盘跳转。
const props = defineProps<{ list?: HallOfFameItem[] }>()
// goto 事件定义保留（父组件已不再用它跳详情），组件本身不再抛出该事件
defineEmits<{ (e: 'goto', id: number): void }>()

/** 有效条目：必须有名称；契约上限 10 条，兜底再切一次 */
const items = computed(() =>
  (props.list ?? [])
    .filter((it) => !!it && typeof it === 'object' && !!(it.short_name || it.name))
    .slice(0, 10),
)

/** 城市 · 国家（缺哪个就不显示，不做占位符） */
function placeOf(it: HallOfFameItem) {
  return [it.city, it.country].filter((s) => !!s && String(s).trim()).join(' · ')
}
</script>

<template>
  <!-- 接口失败 / 空数据时整块隐藏（连标题一起），避免首页出现空白占位 -->
  <section class="section hof" v-if="items.length > 0">
    <div class="section-head">
      <div class="section-heading">
        <h2>🌍 全球标杆展会</h2>
        <p class="section-sub">长期固定在首页展示的精选清单</p>
      </div>
      <!-- 静态清单没有可跳转的列表页，右侧只给条数，不放「查看全部」 -->
      <span class="section-note">共 {{ items.length }} 场</span>
    </div>

    <!-- 横向可滑动：桌面 5 列 × 2 行；窄屏一屏 2 列，左右滑动 -->
    <div class="hof-scroll">
      <article
        v-for="it in items"
        :key="it.id"
        class="hof-card"
        :title="it.name"
      >
        <div class="hof-head">
          <h3 class="hof-name">{{ it.short_name || it.name }}</h3>
          <span class="hof-edition" v-if="it.edition" title="届次">{{ it.edition }}</span>
        </div>
        <p class="hof-place" v-if="placeOf(it)">
          <svg class="pin" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 21s-7-5.686-7-11a7 7 0 1 1 14 0c0 5.314-7 11-7 11Z"
                  fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
            <circle cx="12" cy="10" r="2.4" fill="currentColor" />
          </svg>
          <span>{{ placeOf(it) }}</span>
        </p>
        <p class="hof-tagline" v-if="it.tagline">{{ it.tagline }}</p>
        <span class="hof-sector" v-if="it.sector">{{ it.sector }}</span>
        <!-- 静态精选清单，只做展示，不提供跳转 -->
        <p class="hof-note">展期以官方公布为准</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.section { margin-bottom: var(--space-7); }
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}
.section-heading { min-width: 0; }
.section-head h2 {
  font-size: var(--font-h2);
  line-height: var(--line-h2);
  font-weight: var(--weight-h2);
  color: var(--ink-900);
  letter-spacing: -0.01em;
}
.section-sub {
  margin-top: var(--space-1);
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: var(--ink-500);
}
.section-note {
  flex-shrink: 0;
  font-size: var(--font-sm);
  color: var(--ink-300);
}

/* 横向滚动的网格：列宽固定为 1/5，条目不足 10 条时右侧留白而不是被拉伸 */
.hof-scroll {
  display: grid;
  gap: var(--space-3);
  grid-auto-flow: column;
  grid-template-rows: repeat(2, minmax(0, 1fr));
  grid-auto-columns: calc((100% - 4 * var(--space-3)) / 5);
  overflow-x: auto;
  padding-bottom: var(--space-2);
  scroll-snap-type: x proximity;
  -webkit-overflow-scrolling: touch;
}
.hof-scroll::-webkit-scrollbar { height: 6px; }
.hof-scroll::-webkit-scrollbar-thumb {
  background: var(--ink-100);
  border-radius: var(--radius-full);
}
.hof-scroll::-webkit-scrollbar-thumb:hover { background: var(--ink-300); }

/* 深蓝玻璃感卡片：1px 白色描边 + 顶部高光，不做悬浮位移（不可点击） */
.hof-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-height: 148px;
  padding: var(--space-4);
  border-radius: var(--radius-card);
  color: var(--surface-0);
  background: linear-gradient(160deg, var(--brand-800) 0%, var(--brand-900) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: var(--shadow-card), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  scroll-snap-align: start;
  transition: border-color 0.18s ease;
}
.hof-card:hover { border-color: rgba(255, 255, 255, 0.16); }

.hof-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-2); }
.hof-name {
  font-size: calc(var(--font-sm) + 1px);
  font-weight: 700;
  line-height: 1.35;
  color: var(--surface-0);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hof-edition {
  flex-shrink: 0;
  padding: 1px var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--font-xs);
  font-weight: 600;
  color: var(--accent-400);
  background: var(--brand-700);
  border: 1px solid var(--brand-600);
}
.hof-place {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-xs);
  color: rgba(255, 255, 255, 0.72);
  min-width: 0;
}
.hof-place span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pin { width: 12px; height: 12px; flex-shrink: 0; color: var(--accent-400); }

/* tagline 两行截断（原来三行，卡片更紧凑、更有节奏） */
.hof-tagline {
  flex: 1;
  font-size: var(--font-xs);
  line-height: 1.55;
  color: rgba(255, 255, 255, 0.86);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.hof-sector {
  align-self: flex-start;
  padding: 1px var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--font-xs);
  color: var(--brand-100);
  background: var(--brand-700);
}
/* 右下角浅色小字：精选条目的展期仅供参考，以主办方官方公布为准 */
.hof-note {
  margin-top: auto;
  align-self: flex-end;
  font-size: var(--font-xs);
  line-height: 1.4;
  color: rgba(255, 255, 255, 0.48);
}

@media (max-width: 1024px) {
  .hof-scroll { grid-auto-columns: calc((100% - 2 * var(--space-3)) / 3); }
}
@media (max-width: 768px) {
  /* 移动端：一屏 2 列，继续横向滑动（2 列 × 5 行） */
  .hof-scroll {
    grid-template-rows: repeat(5, minmax(0, 1fr));
    grid-auto-columns: calc((100% - var(--space-3)) / 2);
  }
  .hof-card { min-height: 136px; padding: var(--space-3); }
}
</style>
