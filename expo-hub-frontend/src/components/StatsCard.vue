<script setup lang="ts">
import { useRouter } from 'vue-router'
interface Props { value: string | number; label: string; icon: string; color?: string; trend?: number; to?: string }
const props = defineProps<Props>()
const router = useRouter()
function click() { if (props.to) router.push(props.to) }
</script>

<template>
  <div class="stats-card card" :class="{ clickable: !!to }" @click="click">
    <div class="stats-icon" :style="{ backgroundColor: (color || '#3B82F6') + '18', color: color || '#3B82F6' }">{{ icon }}</div>
    <div class="stats-content"><span class="stats-value">{{ value }}</span><span class="stats-label">{{ label }}</span></div>
  </div>
</template>

<style scoped>
.clickable { cursor: pointer }
.clickable:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.08) }
</style>