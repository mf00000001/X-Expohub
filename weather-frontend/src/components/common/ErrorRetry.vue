<script setup lang="ts">
defineProps<{
  message?: string
}>()

const emit = defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 text-center animate-fade-in">
    <div class="text-5xl mb-4">😞</div>
    <h3 class="text-lg font-semibold text-gray-700 mb-1">加载失败</h3>
    <p class="text-sm text-gray-500 mb-4">
      {{ message || '数据获取失败，请检查网络后重试' }}
    </p>
    <button @click="emit('retry')" class="btn-primary">
      🔄 重新加载
    </button>
  </div>
</template>
