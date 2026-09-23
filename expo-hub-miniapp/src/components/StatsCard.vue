<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  icon?: string
  color?: string
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <view class="stats-card card" @click="$emit('click')">
    <view class="card-body">
      <view class="flex justify-between items-center">
        <view class="stats-left">
          <text class="stats-label text-secondary text-sm">{{ title }}</text>
          <text class="stats-value" :style="color ? `color: ${color}` : ''">{{ value }}</text>
        </view>
        <text v-if="icon" class="stats-icon">{{ icon }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.stats-card {
  flex: 1;
  min-width: 0;
}

.stats-label {
  display: block;
  margin-bottom: 4rpx;
  font-size: 24rpx;
}

.stats-value {
  display: block;
  font-size: 40rpx;
  font-weight: 700;
  line-height: 1.2;
}

.stats-icon {
  font-size: 36rpx;
  opacity: 0.8;
  flex-shrink: 0;
}
</style>
