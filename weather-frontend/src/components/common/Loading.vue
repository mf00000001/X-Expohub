<script setup lang="ts">
withDefaults(
  defineProps<{
    rows?: number
    type?: 'card' | 'list'
  }>(),
  {
    rows: 3,
    type: 'card',
  }
)
</script>

<template>
  <div class="space-y-4 animate-pulse">
    <!-- 卡片骨架 -->
    <div v-if="type === 'card'" class="card">
      <div class="flex justify-between mb-3">
        <div class="h-5 bg-gray-200 rounded w-24" />
        <div class="h-5 bg-gray-200 rounded w-16" />
      </div>
      <div class="flex items-center gap-4">
        <div class="w-16 h-16 bg-gray-200 rounded-full" />
        <div>
          <div class="h-10 bg-gray-200 rounded w-20 mb-1" />
          <div class="h-4 bg-gray-200 rounded w-16" />
        </div>
      </div>
      <div class="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-gray-100">
        <div v-for="n in 3" :key="n" class="h-10 bg-gray-200 rounded" />
      </div>
    </div>

    <!-- 列表骨架 -->
    <div v-for="i in rows" :key="i" class="flex items-center gap-3 p-3">
      <div class="w-12 h-4 bg-gray-200 rounded" />
      <div class="w-8 h-8 bg-gray-200 rounded-full" />
      <div class="flex-1 h-4 bg-gray-200 rounded" />
      <div class="w-16 h-4 bg-gray-200 rounded" />
    </div>
  </div>
</template>
