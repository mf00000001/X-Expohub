<script setup lang="ts">
defineProps<{
  message?: string
  icon?: string
}>()
</script>

<template>
  <view class="empty-state">
    <text class="empty-state-icon">{{ icon || '📭' }}</text>
    <text class="empty-state-text">{{ message || '暂无数据' }}</text>
  </view>
</template>
