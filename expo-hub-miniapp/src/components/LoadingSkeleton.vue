<script setup lang="ts">
defineProps<{
  lines?: number
}>()
</script>

<template>
  <view class="skeleton-container">
    <view class="skeleton-block skeleton-title"></view>
    <view
      v-for="i in (lines || 3)"
      :key="i"
      class="skeleton-block skeleton-line"
      :style="{ width: `${100 - i * 10}%` }"
    ></view>
  </view>
</template>

<style scoped>
.skeleton-container {
  padding: 20px;
}
.skeleton-block {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
  margin-bottom: 12px;
}
.skeleton-title {
  height: 22px;
  width: 60%;
  margin-bottom: 20px;
}
.skeleton-line {
  height: 14px;
}
@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
