<script setup lang="ts">
import { computed } from 'vue'
import { AQI_LEVEL_MAP } from '@/utils/constants'

const props = defineProps<{
  aqi: number
  level: string
  size?: 'sm' | 'md'
}>()

const levelInfo = computed(() => {
  return AQI_LEVEL_MAP[props.level] || AQI_LEVEL_MAP.good
})
</script>

<template>
  <span
    class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-semibold text-xs"
    :class="[
      levelInfo.bg,
      levelInfo.text,
      size === 'sm' ? 'text-[10px] px-2' : '',
    ]"
    :style="{ backgroundColor: levelInfo.color, color: level === 'moderate' ? '#333' : '#fff' }"
  >
    AQI {{ aqi }} {{ levelInfo.label }}
  </span>
</template>
