<script setup lang="ts">
import CategoryGrid from './CategoryGrid.vue'

defineProps<{ interests: string[] }>()
const emit = defineEmits<{ (e: 'update:interests', v: string[]): void }>()

function toggle(cat: string) {
  // Reads parent prop via modelValue pattern — parent handles actual logic
  emit('update:interests', [cat])
}
</script>

<template>
  <div class="picker">
    <p class="picker-hint">选择你感兴趣的行业领域（最少1个，最多5个），我们将为你推荐相关展会</p>
    <slot name="grid" :categories="[]">
      <!-- parent controls selection state via CategoryGrid active prop -->
    </slot>
  </div>
</template>

<style scoped>
.picker { padding: 4px 0; }
.picker-hint { font-size: 14px; color: var(--color-text-secondary); margin-bottom: 20px; text-align: center; }
</style>
