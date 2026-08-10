<script setup lang="ts">
defineProps<{
  message?: string
  icon?: string
}>()
</script>

<template>
  <div class="empty-state">
    <div class="empty-state-icon">{{ icon || '📭' }}</div>
    <p class="empty-state-text">{{ message || '暂无数据' }}</p>
  </div>
</template>
