<script setup lang="ts">
import { computed } from 'vue'
import { getWeatherEmoji } from '@/utils/constants'

const props = withDefaults(
  defineProps<{
    code: string
    size?: 'sm' | 'md' | 'lg' | 'xl'
    isDay?: boolean
  }>(),
  {
    size: 'md',
    isDay: true,
  }
)

const emoji = computed(() => getWeatherEmoji(props.code))

const sizeClass = computed(() => {
  switch (props.size) {
    case 'sm':
      return 'text-xl'
    case 'md':
      return 'text-3xl'
    case 'lg':
      return 'text-5xl'
    case 'xl':
      return 'text-7xl'
    default:
      return 'text-3xl'
  }
})
</script>

<template>
  <span
    class="inline-block leading-none select-none"
    :class="sizeClass"
    role="img"
    :aria-label="code"
  >
    {{ emoji }}
  </span>
</template>
