<script setup lang="ts">
/**
 * 档位徽章。所有颜色由 tone 决定，tone 由 api/persona.ts 里的映射统一给出。
 *
 * 唯一的硬约束：`muted`（unknown/closed）必须是**中性灰 + 虚线边框**，
 * 不能与 `bad`（severe/impossible）共用红色系。
 * 数据缺失不是坏消息；染成警告色等于拿一个缺口去劝退用户。
 */
import type { BandTone } from '@/api/persona'

const props = withDefaults(
  defineProps<{
    band: string
    label: string
    hint?: string
    tone?: BandTone
    /** 徽章右侧的数值，如比值 111.1 */
    value?: string | null
    /** 维度前缀，如 "客群" / "展位" */
    prefix?: string
    size?: 'sm' | 'md'
  }>(),
  { tone: 'muted', value: null, prefix: '', hint: '', size: 'md' },
)
</script>

<template>
  <span
    class="band-badge"
    :class="[`tone-${props.tone}`, `size-${props.size}`]"
    :title="props.hint || undefined"
  >
    <span v-if="props.prefix" class="bb-prefix">{{ props.prefix }}</span>
    <span class="bb-dot" aria-hidden="true"></span>
    <span class="bb-label">{{ props.label }}</span>
    <span v-if="props.value" class="bb-value">{{ props.value }}</span>
  </span>
</template>

<style scoped>
.band-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: var(--radius-full);
  font-size: 12px;
  line-height: 1.5;
  font-weight: 600;
  white-space: nowrap;
  border: 1px solid transparent;
  cursor: help;
}
.size-sm {
  padding: 2px 7px;
  font-size: 11px;
  gap: 4px;
}

.bb-prefix {
  font-weight: 500;
  opacity: 0.75;
}
.bb-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.bb-value {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  padding-left: 5px;
  margin-left: 1px;
  border-left: 1px solid currentColor;
  opacity: 0.9;
}

/* good —— 客源充裕 / 时间充裕 */
.tone-good {
  color: #0f7b52;
  background: #e8f6ef;
  border-color: #bce3d2;
}
/* neutral —— 正常 */
.tone-neutral {
  color: var(--brand-600);
  background: var(--brand-50);
  border-color: var(--brand-100);
}
/* warn —— 偏薄 / 偏紧 */
.tone-warn {
  color: #96620b;
  background: #fdf3e0;
  border-color: #f2dcb2;
}
/* bad —— 摊薄 / 来不及 */
.tone-bad {
  color: #a52a1f;
  background: #fdeceb;
  border-color: #f3c9c4;
}
/* muted —— 无法判断 / 已结束。虚线是刻意的：这是"没有结论"，不是一个结论 */
.tone-muted {
  color: var(--ink-500);
  background: var(--surface-1);
  border: 1px dashed var(--ink-100);
}
/* live —— 进行中。需要立刻行动的，用实心强调 */
.tone-live {
  color: #fff;
  background: var(--accent-600);
  border-color: var(--accent-700);
}
.tone-live .bb-dot {
  animation: live-pulse 1.6s ease-in-out infinite;
}
@keyframes live-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(0.8); }
}
</style>
