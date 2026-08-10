<script setup lang="ts">
import type { DailyForecast } from '@/types/weather'
import { formatTemp, formatDate } from '@/utils/format'
import WeatherIcon from './WeatherIcon.vue'

defineProps<{
  daily: DailyForecast[]
}>()

const emit = defineEmits<{
  select: [date: string]
}>()
</script>

<template>
  <div class="card">
    <h3 class="text-base font-semibold text-gray-700 mb-3">📅 7日预报</h3>
    <div class="space-y-2">
      <div
        v-for="(day, index) in daily"
        :key="day.date"
        @click="emit('select', day.date)"
        class="flex items-center gap-3 p-2 rounded-xl hover:bg-gray-50 cursor-pointer transition-colors"
      >
        <span class="w-16 text-sm text-gray-600 shrink-0">
          {{ index === 0 ? '今天' : formatDate(day.date, true) }}
        </span>
        <WeatherIcon :code="day.weather_code" size="sm" :is-day="true" />
        <span class="text-xs text-gray-500 w-20 shrink-0 truncate">
          {{ day.weather_text }}
        </span>
        <!-- 温度条 -->
        <div class="flex-1 flex items-center gap-2">
          <span class="text-sm text-blue-500 font-medium w-10 text-right">
            {{ formatTemp(day.temp_min, false) }}°
          </span>
          <div class="flex-1 h-1.5 rounded-full bg-gradient-to-r from-blue-400 via-yellow-400 to-red-400 relative">
            <div
              class="absolute h-4 w-4 rounded-full bg-white border-2 border-blue-400 -top-[5px] shadow-sm"
              :style="{ left: '20%' }"
            />
          </div>
          <span class="text-sm text-red-500 font-medium w-10">
            {{ formatTemp(day.temp_max, false) }}°
          </span>
        </div>
        <div class="flex items-center gap-3 text-xs text-gray-400">
          <span>💧{{ day.humidity }}%</span>
          <span v-if="day.pop > 0">🌧️{{ day.pop }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>
