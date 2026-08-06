<script setup lang="ts">
interface Props {
  value: string | number
  label: string
  icon: string
  color?: string
  trend?: number
}

defineProps<Props>()
</script>

<template>
  <div class="stats-card card">
    <div class="stats-icon" :style="{ backgroundColor: (color || '#3B82F6') + '18', color: color || '#3B82F6' }">
      {{ icon }}
    </div>
    <div class="stats-content">
      <span class="stats-value">{{ value }}</span>
      <span class="stats-label">{{ label }}</span>
    </div>
    <div v-if="trend !== undefined" class="stats-trend" :class="trend >= 0 ? 'trend-up' : 'trend-down'">
      {{ trend >= 0 ? '↑' : '↓' }} {{ Math.abs(trend) }}%
    </div>
  </div>
</template>

<style scoped>
.stats-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
}

.stats-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.stats-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.stats-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stats-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.stats-trend {
  font-size: 13px;
  font-weight: 500;
}
.trend-up {
  color: var(--success);
}
.trend-down {
  color: var(--danger);
}
</style>
