<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  icon?: string
  color?: string
}>()
</script>

<template>
  <div class="stats-card card">
    <div class="card-body">
      <div class="flex justify-between items-center">
        <div>
          <p class="stats-label text-secondary text-sm">{{ title }}</p>
          <p class="stats-value" :style="{ color: color || 'var(--color-text)' }">{{ value }}</p>
        </div>
        <div class="stats-icon" v-if="icon">{{ icon }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-card {
  transition: box-shadow 0.2s;
}
.stats-card:hover {
  box-shadow: var(--shadow-md);
}
.stats-label {
  margin-bottom: 4px;
}
.stats-value {
  font-size: 32px;
  font-weight: 700;
}
.stats-icon {
  font-size: 36px;
  opacity: 0.8;
}
</style>
