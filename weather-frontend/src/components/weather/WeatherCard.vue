<script setup lang="ts">
import type { CurrentWeather } from '@/types/weather'
import { formatTemp } from '@/utils/format'
import { getWeatherEmoji } from '@/utils/constants'

const props = defineProps<{ weather: CurrentWeather; compact?: boolean }>()
const emit = defineEmits<{ click: [] }>()
</script>

<template>
  <div @click="emit('click')" class="card cursor-pointer hover:shadow-lg transition-all duration-300" :class="compact ? 'p-4' : 'p-5 sm:p-6'">
    <div class="flex items-center justify-between mb-3">
      <div>
        <h3 class="text-lg sm:text-xl font-semibold text-gray-800">{{ weather.city_name }}</h3>
        <p class="text-xs text-gray-400">{{ weather.country }}</p>
      </div>
    </div>

    <div class="flex items-center gap-4 sm:gap-6">
      <div class="text-4xl">{{ getWeatherEmoji(weather.weather_code) }}</div>
      <div>
        <div class="text-4xl sm:text-5xl font-bold text-gray-900 tracking-tight">
          {{ formatTemp(weather.temperature) }}
        </div>
        <p class="text-sm text-gray-500 mt-0.5">体感 {{ formatTemp(weather.feels_like) }}</p>
      </div>
    </div>

    <p class="text-base text-gray-600 mt-3 font-medium">{{ weather.weather_text }}</p>

    <div class="grid grid-cols-3 gap-3 mt-4 text-sm text-gray-600">
      <div class="text-center p-2 bg-gray-50 rounded-lg">
        <p class="text-xs text-gray-400">湿度</p>
        <p class="font-semibold">{{ weather.humidity }}%</p>
      </div>
      <div class="text-center p-2 bg-gray-50 rounded-lg">
        <p class="text-xs text-gray-400">风速</p>
        <p class="font-semibold">{{ weather.wind_speed }} km/h</p>
      </div>
      <div class="text-center p-2 bg-gray-50 rounded-lg">
        <p class="text-xs text-gray-400">{{ weather.wind_direction_text }}</p>
        <p class="font-semibold">{{ weather.pressure }} hPa</p>
      </div>
    </div>
  </div>
</template>
