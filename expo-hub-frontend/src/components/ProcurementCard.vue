<script setup lang="ts">
import { computed } from 'vue'
import { formatDate, formatPrice } from '@/utils/format'

const props = defineProps<{ procurement: Record<string, any> }>()

const id = computed(() => props.procurement.id)
const title = computed(() => props.procurement.title || '')
const category = computed(() => props.procurement.category || '')
const budgetMin = computed(() => props.procurement.budget_min || props.procurement.budgetMin || 0)
const budgetMax = computed(() => props.procurement.budget_max || props.procurement.budgetMax || 0)
const status = computed(() => props.procurement.status || '')
const deadline = computed(() => props.procurement.deadline || '')
const matchCount = computed(() => props.procurement.match_count || props.procurement.matchCount || 0)

const statusLabelMap: Record<string, string> = {
  open: '进行中', published: '进行中',
  closed: '已截止', cancelled: '已取消',
  matched: '已匹配', completed: '已完成',
}

const statusClass = computed(() => {
  const s = status.value
  if (s === 'published' || s === 'open') return 'tag-success'
  if (s === 'matched' || s === 'completed') return 'tag-info'
  return 'tag-warning'
})
</script>

<template>
  <div class="procurement-card card" @click="$emit('click', id)">
    <div class="procurement-header">
      <h4 class="procurement-title">{{ title }}</h4>
      <span class="tag" :class="statusClass">
        {{ statusLabelMap[status] || status }}
      </span>
    </div>
    <div class="procurement-body">
      <span class="procurement-category tag tag-primary">{{ category }}</span>
      <span class="procurement-budget">
        💰 {{ formatPrice(budgetMin) }} ~ {{ formatPrice(budgetMax) }}
      </span>
    </div>
    <div class="procurement-footer">
      <span class="deadline">⏰ 截止: {{ formatDate(deadline) }}</span>
      <span class="match-count">🎯 {{ matchCount }} 个匹配</span>
    </div>
  </div>
</template>


<style scoped>
.procurement-card {
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.procurement-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.procurement-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--spacing-sm);
}

.procurement-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  line-height: 1.4;
}

.procurement-body {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.procurement-budget {
  font-size: 14px;
  color: var(--text-secondary);
}

.procurement-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-hint);
}
</style>
