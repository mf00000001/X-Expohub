<script setup lang="ts">
import type { Procurement } from '@/api/procurement'

defineProps<{
  procurement: Procurement
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <div class="procurement-card card" @click="$emit('click')">
    <div class="card-body">
      <div class="flex justify-between items-start mb-2">
        <h3 class="procurement-title">{{ procurement.title }}</h3>
        <span class="tag" :class="procurement.status === 'open' ? 'tag-green' : 'tag-gray'">
          {{ procurement.status === 'open' ? '进行中' : procurement.status === 'closed' ? '已关闭' : procurement.status }}
        </span>
      </div>
      <p class="text-secondary text-sm">{{ procurement.description?.slice(0, 100) }}{{ procurement.description?.length > 100 ? '...' : '' }}</p>
      <div class="procurement-meta flex gap-4 mt-4 text-sm text-secondary">
        <span v-if="procurement.category">🏷 {{ procurement.category }}</span>
        <span v-if="procurement.quantity">📊 {{ procurement.quantity }}{{ procurement.unit ? ` ${procurement.unit}` : '' }}</span>
        <span v-if="procurement.budget">💰 ¥{{ procurement.budget }}</span>
        <span v-if="procurement.deadline">⏰ {{ procurement.deadline }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.procurement-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.procurement-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.procurement-title {
  font-size: 17px;
  font-weight: 600;
  flex: 1;
}
.procurement-meta {
  flex-wrap: wrap;
}
</style>
