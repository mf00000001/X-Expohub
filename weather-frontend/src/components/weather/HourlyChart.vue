<script setup lang="ts">
import { ref } from 'vue'
import type { HourlyForecast } from '@/types/weather'
import { formatTemp, formatTime } from '@/utils/format'
import WeatherIcon from './WeatherIcon.vue'

defineProps<{
  hourly: HourlyForecast[]
}>()

const scrollContainer = ref<HTMLElement | null>(null)

function scrollLeft() {
  scrollContainer.value?.scrollBy({ left: -200, behavior: 'smooth' })
}

function scrollRight() {
  scrollContainer.value?.scrollBy({ left: 200, behavior: 'smooth' })
}
</script>

<template>
  <div class="card relative">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-base font-semibold text-gray-700">⏰ 逐小时预报</h3>
      <div class="flex gap-1">
        <button
          @click="scrollLeft"
          class="w-7 h-7 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors"
        >
          ‹
        </button>
        <button
          @click="scrollRight"
          class="w-7 h-7 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors"
        >
          ›
        </button>
      </div>
    </div>
    <div
      ref="scrollContainer"
      class="flex gap-3 overflow-x-auto pb-2 scroll-smooth snap-x snap-mandatory"
    >
      <div
        v-for="(h, idx) in hourly"
        :key="h.time"
        class="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-gray-50 hover:bg-blue-50 transition-colors min-w-[72px] snap-start"
        :class="{ 'bg-blue-50 ring-1 ring-blue-200': idx === 0 }"
      >
        <span class="text-xs text-gray-500 font-medium">
          {{ idx === 0 ? '现在' : formatTime(h.time) }}
        </span>
        <WeatherIcon :code="h.weather_code" size="sm" :is-day="h.is_day" />
        <span class="text-sm font-bold text-gray-800">
          {{ formatTemp(h.temperature, false) }}°
        </span>
        <div class="flex flex-col items-center gap-0.5">
          <span class="text-[10px] text-gray-400">💧{{ h.humidity }}%</span>
          <span v-if="h.pop > 0" class="text-[10px] text-blue-400">
            🌧️{{ h.pop }}%
          </span>
        </div>
      </div>

      <!-- 空状态 -->
      <div
        v-if="!hourly || hourly.length === 0"
        class="flex items-center justify-center w-full py-6 text-gray-400 text-sm"
      >
        暂无逐小时数据
      </div>
    </div>
  </div>
</template>
