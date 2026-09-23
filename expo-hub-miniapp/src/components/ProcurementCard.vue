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
  <view class="procurement-card card" @click="$emit('click')">
    <view class="card-body">
      <view class="flex justify-between items-start mb-2">
        <text class="procurement-title">{{ procurement.title }}</text>
        <text class="tag" :class="procurement.status === 'open' ? 'tag-green' : 'tag-gray'">
          {{ procurement.status === 'open' ? '进行中' : procurement.status === 'closed' ? '已关闭' : procurement.status }}
        </text>
      </view>
      <text class="text-secondary text-sm block">
        {{ procurement.description?.slice(0, 100) }}{{ procurement.description?.length > 100 ? '...' : '' }}
      </text>
      <view class="procurement-meta flex gap-4 mt-4 text-sm text-secondary">
        <text v-if="procurement.category">🏷 {{ procurement.category }}</text>
        <text v-if="procurement.quantity">📊 {{ procurement.quantity }}{{ procurement.unit ? ` ${procurement.unit}` : '' }}</text>
        <text v-if="procurement.budget">💰 ¥{{ procurement.budget }}</text>
        <text v-if="procurement.deadline">⏰ {{ procurement.deadline }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.procurement-title {
  font-size: 17px;
  font-weight: 600;
  flex: 1;
  padding-right: 8px;
}

.block {
  display: block;
}

.procurement-meta {
  flex-wrap: wrap;
}
</style>
