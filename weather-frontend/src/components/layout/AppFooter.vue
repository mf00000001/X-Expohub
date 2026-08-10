<script setup lang="ts">
const currentYear = new Date().getFullYear()
</script>

<template>
  <footer class="border-t border-gray-200 bg-white/60 mt-auto">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div class="flex flex-col sm:flex-row items-center justify-between gap-2 text-sm text-gray-500">
        <div class="flex items-center gap-1">
          <span>🌤️</span>
          <span>天气查询平台 &copy; {{ currentYear }}</span>
        </div>
        <div class="flex items-center gap-4">
          <span>数据来源：开放气象数据</span>
          <span class="hidden sm:inline">|</span>
          <span>仅供参考</span>
        </div>
      </div>
    </div>
  </footer>
</template>
