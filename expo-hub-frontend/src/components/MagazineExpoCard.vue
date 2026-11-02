<script setup lang="ts">
import { computed } from 'vue'
import type { Exhibition } from '@/api/exhibition'
import ExpoCover from '@/components/ExpoCover.vue'

// 杂志式展会卡：精选区「1 大 + 2 小」共用。
// 数据原样取自 GET /exhibitions/featured 的条目，日期/地点只做格式化，不补造。
// 只有真实展会 id（>0）才可点击跳详情；无 id 时降级为静态卡。
const props = withDefaults(defineProps<{
  exhibition: Exhibition
  /** large = 16:9 大图主卡；small = 左图右文的紧凑卡 */
  variant?: 'large' | 'small'
}>(), { variant: 'large' })

const emit = defineEmits<{ (e: 'click', id: number): void }>()

const id = computed(() => {
  const n = Number((props.exhibition as any)?.id)
  return Number.isFinite(n) && n > 0 ? n : 0
})
const title = computed(() => (props.exhibition as any)?.title || (props.exhibition as any)?.name || '')
const cover = computed(() => {
  const e: any = props.exhibition || {}
  return e.cover_image || e.cover_url || e.cover_image_url || ''
})
const place = computed(() => {
  const e: any = props.exhibition || {}
  return e.venue || e.location || ''
})

const startDate = computed(() => (props.exhibition as any)?.start_date || (props.exhibition as any)?.startDate || '')
const endDate = computed(() => (props.exhibition as any)?.end_date || (props.exhibition as any)?.endDate || '')

/** MM.DD：日期非法/缺失返回空串，不显示占位日期 */
function md(value?: string): string {
  if (!value) return ''
  const d = new Date(value)
  if (!Number.isFinite(d.getTime())) return ''
  return `${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

const dateRange = computed(() => {
  const a = md(startDate.value)
  const b = md(endDate.value)
  if (a && b) return a === b ? a : `${a} – ${b}`
  return a || b
})

/** 状态三态：与 Hero 轮播同一口径（用户视角，日期优先） */
type CardStatus = 'upcoming' | 'ongoing' | 'ended'

/** 日期解析：缺失/非法一律返回 null（不把坏数据当成「今天」） */
function parseDate(value?: string): Date | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isFinite(d.getTime()) ? d : null
}

/**
 * 状态推导：先看结束日期、再看开始日期；
 * 两个日期都缺失或非法时，才回退到后端 status 的明确取值，仍不明确则按「即将开幕」占位。
 */
function statusOf(e: any): CardStatus {
  const now = Date.now()
  const end = parseDate(e?.end_date || e?.endDate)
  const start = parseDate(e?.start_date || e?.startDate)
  if (end && now > end.getTime()) return 'ended'
  if (start && now >= start.getTime()) return 'ongoing'
  if (start) return 'upcoming'
  const st = String(e?.status || '')
  if (st === 'ongoing') return 'ongoing'
  if (st === 'finished' || st === 'ended' || st === 'cancelled') return 'ended'
  return 'upcoming'
}

const statusType = computed<CardStatus>(() => statusOf(props.exhibition))

/** 状态徽章文案：配色见样式 .mag-status.upcoming / .ongoing / .ended */
const statusLabel = computed(() => ({
  upcoming: '即将开幕',
  ongoing: '进行中',
  ended: '已结束',
} as Record<CardStatus, string>)[statusType.value])

function activate() {
  if (id.value > 0) emit('click', id.value)
}
</script>

<template>
  <article
    class="mag-card"
    :class="[variant, { clickable: id > 0 }]"
    :role="id > 0 ? 'link' : undefined"
    :tabindex="id > 0 ? 0 : undefined"
    @click="activate"
    @keydown.enter="activate"
  >
    <div class="mag-cover">
      <!-- 封面：有图出图；cover_image 为空串或图片 404 时由 ExpoCover 落到品牌渐变兜底，不出破图图标 -->
      <ExpoCover class="mag-cover-media" :src="cover" :title="title" ratio="16/9" />
      <!-- 大卡：日期徽章 + 状态徽章并排压在封面上 -->
      <div class="mag-badges" v-if="variant === 'large'">
        <span class="mag-date" v-if="dateRange">{{ dateRange }}</span>
        <span class="mag-status" :class="statusType">{{ statusLabel }}</span>
      </div>
    </div>

    <div class="mag-body">
      <!-- 小卡：日期与状态写在文字区，避免在小图上压字 -->
      <div class="mag-meta" v-if="variant === 'small'">
        <span class="mag-date-inline" v-if="dateRange">{{ dateRange }}</span>
        <span class="mag-status" :class="statusType">{{ statusLabel }}</span>
      </div>
      <h3 class="mag-title">{{ title }}</h3>
      <p class="mag-place" v-if="place">
        <svg class="pin" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 21s-7-5.686-7-11a7 7 0 1 1 14 0c0 5.314-7 11-7 11Z"
                fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
          <circle cx="12" cy="10" r="2.4" fill="currentColor" />
        </svg>
        <span>{{ place }}</span>
      </p>
    </div>
  </article>
</template>

<style scoped>
.mag-card {
  display: flex;
  flex-direction: column;
  /* 作为精选区 flex 子项时可以被压缩到列高，配合父级 stretch 铺满不留白 */
  min-height: 0;
  overflow: hidden;
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.18s ease;
}
.mag-card.clickable { cursor: pointer; }
.mag-card:hover { box-shadow: var(--shadow-hover); }
.mag-card:focus-visible {
  outline: 2px solid var(--brand-500);
  outline-offset: 2px;
}

.mag-cover {
  position: relative;
  overflow: hidden;
  aspect-ratio: 16 / 9;
  background: linear-gradient(150deg, var(--brand-800) 0%, var(--brand-600) 100%);
}
/* 封面组件铺满封面位：大卡吃 16/9，小卡跟随卡片 stretch 后的高度 */
.mag-cover :deep(.mag-cover-media) {
  width: 100%;
  height: 100%;
  /* hover 轻微放大：120ms，克制不晃眼 */
  transition: transform 120ms ease;
}
.mag-card:hover :deep(.mag-cover-media) { transform: scale(1.03); }

/* 大卡被父级拉伸时由封面吸收多出来的高度，图片 cover 自适应，文字下方不留白 */
.mag-card.large .mag-cover { flex: 1 1 auto; }
.mag-card.large .mag-body { flex: 0 0 auto; }

.mag-badges {
  position: absolute;
  top: var(--space-4);
  left: var(--space-4);
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}
.mag-date {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-btn);
  font-size: var(--font-xs);
  font-weight: 700;
  letter-spacing: 0.04em;
  font-variant-numeric: tabular-nums;
  color: var(--brand-950);
  background: var(--accent-500);
}

/* 状态徽章：底色即状态语义，与 Hero 角标同一套映射，全部走品牌令牌 */
.mag-status {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--font-xs);
  font-weight: 700;
  letter-spacing: 0.02em;
  white-space: nowrap;
  color: var(--brand-950);
  box-shadow: var(--shadow-card);
}
.mag-status.upcoming { background: var(--accent-500); }
.mag-status.ongoing { background: var(--success); }
.mag-status.ended { background: var(--ink-300); }

.mag-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-5);
  min-height: 0;
}
.mag-title {
  font-size: calc(var(--font-h3) + 2px);
  font-weight: 700;
  line-height: 1.35;
  color: var(--ink-900);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.mag-place {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-sm);
  color: var(--ink-500);
  min-width: 0;
}
.mag-place span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pin {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: var(--ink-300);
}

/* 小卡：左图右文，紧凑；日期与状态改到文字区 */
.mag-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}
.mag-date-inline {
  font-size: var(--font-xs);
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--accent-700);
  font-variant-numeric: tabular-nums;
}
.mag-card.small { flex-direction: row; align-items: stretch; }
.mag-card.small .mag-cover {
  width: 40%;
  flex: 0 0 40%;
  min-width: 112px;
  aspect-ratio: auto;
  min-height: 104px;
  /* 高度跟随卡片：小卡被 stretch 拉高时图片自动 cover 填满，不出现空白 */
  align-self: stretch;
}
.mag-card.small .mag-meta { margin-bottom: var(--space-1); }
.mag-card.small .mag-status { box-shadow: none; }
.mag-card.small .mag-body {
  padding: var(--space-4);
  justify-content: center;
  gap: var(--space-1);
  min-width: 0;
}
.mag-card.small .mag-title { font-size: var(--font-body); line-height: 1.4; }

@media (max-width: 768px) {
  .mag-card.small .mag-cover { min-width: 104px; }
  .mag-card .mag-body { padding: var(--space-4); }
}
</style>
