<script setup lang="ts">
import { computed } from 'vue'
import type { PublicStatRecent } from '@/api/stats'

// 「实时动态」独立区块：展会 / 采购需求的新发布记录。
// 数据仍由父组件从 GET /stats/public 的 recent 传入（本组件不重复请求）；
// 全部来自数据库真实记录，没有模拟数据，也没有定时轮转的假动态。
// 视觉：浅底卡片 + 左侧 6px 金色竖条 + 时间右对齐，整体更轻。
const props = defineProps<{ recent?: PublicStatRecent[] }>()

const items = computed(() => (props.recent ?? []).filter(a => !!a && !!a.title))

function iconOf(type: string) {
  return ({ exhibition: '🎪', product: '📦', procurement: '🛒' } as Record<string, string>)[type] || '📌'
}

function labelOf(type: string) {
  return ({ exhibition: '新展会上线', product: '新展品上架', procurement: '新增采购需求' } as Record<string, string>)[type] || '有新动态'
}

/** 把 ISO 时间转成「x 分钟前」；时间缺失或非法时返回空串（不编造时间） */
function timeAgo(at?: string | null) {
  if (!at) return ''
  const t = new Date(at).getTime()
  if (!Number.isFinite(t)) return ''
  const diff = Date.now() - t
  if (diff <= 0) return '刚刚'
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min}分钟前`
  const hour = Math.floor(min / 60)
  if (hour < 24) return `${hour}小时前`
  const day = Math.floor(hour / 24)
  if (day < 30) return `${day}天前`
  const d = new Date(t)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}
</script>

<template>
  <section class="section feed">
    <div class="section-head">
      <div class="section-heading">
        <h2>📣 实时动态</h2>
        <p class="section-sub">新上线的展会与采购需求，先看到先对接</p>
      </div>
      <span class="section-note" v-if="items.length">{{ items.length }} 条</span>
    </div>

    <div class="feed-card" v-if="items.length > 0">
      <div class="feed-item" v-for="(a, i) in items" :key="i">
        <span class="feed-bar" aria-hidden="true"></span>
        <span class="feed-icon" aria-hidden="true">{{ iconOf(a.type) }}</span>
        <span class="feed-text">{{ labelOf(a.type) }}：{{ a.title }}</span>
        <span class="feed-time" v-if="timeAgo(a.at)">{{ timeAgo(a.at) }}</span>
      </div>
    </div>
    <div class="feed-empty" v-else>暂无动态</div>
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

/* 浅底卡片：不加阴影，靠底色与 1px 描边区分层级 */
.feed-card {
  padding: 0 var(--space-5);
  background: var(--surface-1);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
}
.feed-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--ink-100);
}
.feed-item:last-child { border-bottom: none; }

/* 条目左侧 6px 金色竖条：整条高度，圆头 */
.feed-bar {
  flex-shrink: 0;
  align-self: stretch;
  width: 6px;
  min-height: 18px;
  border-radius: var(--radius-full);
  background: var(--accent-500);
}
.feed-icon { flex-shrink: 0; font-size: var(--font-sm); }
.feed-text {
  flex: 1;
  min-width: 0;
  font-size: var(--font-sm);
  color: var(--ink-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.feed-time {
  flex-shrink: 0;
  font-size: var(--font-xs);
  color: var(--ink-300);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.feed-empty {
  padding: var(--space-5) 0;
  text-align: center;
  font-size: var(--font-sm);
  color: var(--ink-500);
  background: var(--surface-1);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
}
</style>
