<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Exhibition } from '@/api/exhibition'

// 「重磅发布」= 即将举办的展会（原「重磅来袭」的位置）。
// 数据由父组件 HomeView 请求 GET /exhibitions/upcoming 后传入（一次取满 100 条），
// 本组件只做「查看更多」的前端切片，不重复请求、不编造条数。
// 视觉改为「按月份分组的纵向时间轴」，日期/地点/状态全部来自列表真实字段。
const props = defineProps<{ list?: Exhibition[] }>()
const emit = defineEmits<{ (e: 'goto', id: number): void }>()

/** 每次点「查看更多」多展示的条数 */
const PAGE_STEP = 8

const items = computed(() => props.list ?? [])
const visibleCount = ref(PAGE_STEP)
const shown = computed(() => items.value.slice(0, visibleCount.value))
/** 还有多少场没展开（按钮文案用它，数字来自真实列表长度） */
const restCount = computed(() => Math.max(items.value.length - visibleCount.value, 0))
const hasMore = computed(() => restCount.value > 0)

// 数据刷新（重新请求 / 路由回来）后回到首屏 8 条
watch(() => items.value.length, () => { visibleCount.value = PAGE_STEP })

function showMore() { visibleCount.value += PAGE_STEP }

function open(id: number) {
  if (typeof id === 'number' && id > 0) emit('goto', id)
}

type StatusType = 'upcoming' | 'ongoing' | 'ended' | 'unknown'

interface TimelineRow {
  key: string
  id: number
  title: string
  place: string
  day: string
  month: string
  statusType: StatusType
  status: string
}

interface TimelineGroup {
  key: string
  label: string
  rows: TimelineRow[]
}

function parseDate(value?: string): Date | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isFinite(d.getTime()) ? d : null
}

/** 状态：优先按日期推导（用户视角），日期缺失时回退到后端 status，不做推断 */
function statusTypeOf(e: any, start: Date | null): StatusType {
  const end = parseDate(e?.end_date || e?.endDate)
  const now = Date.now()
  if (end && now > end.getTime()) return 'ended'
  if (start && now >= start.getTime()) return 'ongoing'
  if (start) return 'upcoming'
  const st = String(e?.status || '')
  if (st === 'ongoing') return 'ongoing'
  if (st === 'finished' || st === 'ended' || st === 'cancelled') return 'ended'
  return 'unknown'
}

function statusLabel(type: StatusType, e: any): string {
  if (type === 'upcoming') return '即将举办'
  if (type === 'ongoing') return '进行中'
  if (type === 'ended') return '已结束'
  const st = String(e?.status || '')
  return ({ published: '已发布', pending: '待审核', draft: '草稿' } as Record<string, string>)[st] || '待定'
}

function toRow(e: any, start: Date | null): TimelineRow {
  const statusType = statusTypeOf(e, start)
  return {
    key: `${e?.id ?? 'x'}-${e?.start_date ?? ''}`,
    id: Number(e?.id) || 0,
    title: e?.title || e?.name || '',
    place: e?.location || e?.venue || '',
    day: start ? String(start.getDate()).padStart(2, '0') : '—',
    month: start ? `${start.getMonth() + 1}月` : '待定',
    statusType,
    status: statusLabel(statusType, e),
  }
}

/** 按「年-月」分组，保持接口原有顺序（upcoming 已按开始日期先后返回） */
const groups = computed<TimelineGroup[]>(() => {
  const map = new Map<string, TimelineGroup>()
  for (const e of shown.value) {
    const start = parseDate((e as any)?.start_date || (e as any)?.startDate)
    const key = start ? `${start.getFullYear()}-${start.getMonth() + 1}` : 'tbd'
    const label = start ? `${start.getFullYear()}年${start.getMonth() + 1}月` : '日期待定'
    let group = map.get(key)
    if (!group) {
      group = { key, label, rows: [] }
      map.set(key, group)
    }
    group.rows.push(toRow(e, start))
  }
  return Array.from(map.values())
})
</script>

<template>
  <section class="section upcoming">
    <div class="section-head">
      <div class="section-heading">
        <h2>🚀 重磅发布</h2>
        <p class="section-sub">
          即将举办的展会，先看排期再定行程<template v-if="items.length"> · 共 {{ items.length }} 场</template>
        </p>
      </div>
      <button v-if="hasMore" class="section-more" @click="showMore">
        查看更多（还有 {{ restCount }} 场）→
      </button>
    </div>

    <!-- 纵向时间轴：左侧 2px 竖线 + 10px 金色节点，按月份分组 -->
    <div class="timeline" v-if="groups.length > 0">
      <div class="tl-group" v-for="g in groups" :key="g.key">
        <p class="tl-month">{{ g.label }}</p>
        <ul class="tl-list">
          <li
            v-for="row in g.rows"
            :key="row.key"
            class="tl-item"
            :class="{ clickable: row.id > 0 }"
            :role="row.id > 0 ? 'link' : undefined"
            :tabindex="row.id > 0 ? 0 : undefined"
            @click="open(row.id)"
            @keydown.enter="open(row.id)"
          >
            <span class="tl-dot" aria-hidden="true"></span>
            <div class="tl-date">
              <strong>{{ row.day }}</strong>
              <span>{{ row.month }}</span>
            </div>
            <div class="tl-body">
              <h3 class="tl-title">{{ row.title }}</h3>
              <p class="tl-place" v-if="row.place">
                <svg class="pin" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 21s-7-5.686-7-11a7 7 0 1 1 14 0c0 5.314-7 11-7 11Z"
                        fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
                  <circle cx="12" cy="10" r="2.4" fill="currentColor" />
                </svg>
                <span>{{ row.place }}</span>
              </p>
            </div>
            <span class="tl-status" :class="row.statusType">{{ row.status }}</span>
          </li>
        </ul>
      </div>
    </div>

    <!-- 空态：不占位、不编造展会，只给一句可核对的提示 -->
    <div class="upcoming-empty" v-else>
      <span class="empty-icon">🗓️</span>
      <p class="empty-text">近期暂无新展，敬请关注</p>
    </div>

    <p class="upcoming-count" v-if="hasMore">已展示 {{ shown.length }} / {{ items.length }} 场</p>
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
.section-more {
  flex-shrink: 0;
  padding: 0;
  border: none;
  background: none;
  font-size: var(--font-sm);
  font-weight: 600;
  color: var(--brand-600);
  cursor: pointer;
  transition: color 0.15s ease;
}
.section-more:hover { color: var(--brand-800); }

/* ---------- 时间轴 ---------- */
.timeline { position: relative; }
/* 贯穿所有月份的竖线（z-index 高于行背景，hover 时不会被盖住） */
.timeline::before {
  content: '';
  position: absolute;
  left: 4px;
  top: var(--space-2);
  bottom: var(--space-2);
  width: 2px;
  background: var(--ink-100);
  z-index: 1;
}
.tl-group + .tl-group { margin-top: var(--space-5); }
.tl-month {
  padding-left: 32px;
  margin-bottom: var(--space-2);
  font-size: var(--font-xs);
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--ink-500);
}
.tl-list { list-style: none; }
.tl-item {
  position: relative;
  z-index: 0;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4) var(--space-3) 32px;
  border-radius: var(--radius-btn);
  transition: background 0.15s ease;
}
.tl-item.clickable { cursor: pointer; }
.tl-item:hover { background: var(--surface-1); }
.tl-item:focus-visible { outline: 2px solid var(--brand-500); outline-offset: 2px; }
/* 每个节点一个 10px 金色圆点，白环让竖线在点后断开 */
.tl-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  background: var(--accent-500);
  box-shadow: 0 0 0 4px var(--surface-0);
  z-index: 2;
}
.tl-date {
  flex: 0 0 56px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.2;
}
.tl-date strong {
  font-size: var(--font-h3);
  font-weight: 800;
  color: var(--accent-600);
  font-variant-numeric: tabular-nums;
}
.tl-date span { font-size: var(--font-xs); color: var(--ink-500); }

.tl-body { flex: 1; min-width: 0; }
.tl-title {
  font-size: var(--font-body);
  font-weight: 600;
  line-height: 1.45;
  color: var(--ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.tl-place {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1);
  font-size: var(--font-xs);
  color: var(--ink-500);
  min-width: 0;
}
.tl-place span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pin { width: 12px; height: 12px; flex-shrink: 0; color: var(--ink-300); }

.tl-status {
  flex-shrink: 0;
  padding: 2px var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--font-xs);
  font-weight: 600;
  white-space: nowrap;
}
.tl-status.upcoming { color: var(--accent-700); background: var(--accent-100); }
.tl-status.ongoing { color: var(--brand-700); background: var(--brand-100); }
.tl-status.ended { color: var(--ink-500); background: var(--surface-2); }
.tl-status.unknown { color: var(--ink-500); background: var(--surface-2); }

.upcoming-count {
  margin-top: var(--space-4);
  font-size: var(--font-xs);
  color: var(--ink-300);
  text-align: center;
}

.upcoming-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8) var(--space-4);
  border-radius: var(--radius-card);
  background: var(--surface-1);
  border: 1px dashed var(--ink-100);
}
.upcoming-empty .empty-icon { font-size: var(--font-h1); margin-bottom: var(--space-3); }
.upcoming-empty .empty-text { font-size: var(--font-sm); color: var(--ink-500); }

@media (max-width: 640px) {
  .tl-item { gap: var(--space-2); padding-right: var(--space-2); }
  .tl-date { flex-basis: 44px; }
  .tl-date strong { font-size: var(--font-body); }
  .tl-status { padding: 2px var(--space-1); }
}
</style>
