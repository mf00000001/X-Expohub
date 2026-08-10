<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWeatherStore } from '@/stores/weather'
import { formatTemp, formatDate } from '@/utils/format'
import WeatherIcon from '@/components/weather/WeatherIcon.vue'
import Loading from '@/components/common/Loading.vue'
import ErrorRetry from '@/components/common/ErrorRetry.vue'

const route = useRoute()
const router = useRouter()
const weatherStore = useWeatherStore()
const cityId = Number(route.params.id)

onMounted(() => {
  if (cityId) {
    weatherStore.fetchDaily(cityId, 15)
    weatherStore.fetchCurrent(cityId)
  }
})
</script>

<template>
  <div class="space-y-5 animate-fade-in">
    <button @click="router.back()" class="btn-secondary text-sm !px-3 !py-1.5">
      ← 返回
    </button>

    <h1 class="text-xl font-bold text-gray-800">
      📅 15日天气预报
      <span v-if="weatherStore.current" class="text-base font-normal text-gray-500 ml-2">
        - {{ weatherStore.current.city_name }}
      </span>
    </h1>

    <Loading v-if="weatherStore.loading && !weatherStore.daily.length" :rows="8" type="list" />
    <ErrorRetry
      v-else-if="weatherStore.error && !weatherStore.daily.length"
      :message="weatherStore.error"
      @retry="weatherStore.fetchDaily(cityId, 15)"
    />

    <div v-else class="card">
      <div class="space-y-3">
        <div
          v-for="(day, idx) in weatherStore.daily"
          :key="day.date"
          class="flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 transition-colors"
          :class="{ 'bg-blue-50': idx === 0 }"
        >
          <!-- 日期 -->
          <div class="w-24 shrink-0">
            <p class="text-sm font-medium text-gray-800">
              {{ idx === 0 ? '今天' : formatDate(day.date, true) }}
            </p>
            <p class="text-xs text-gray-400">{{ day.date.slice(5) }}</p>
          </div>

          <!-- 天气图标 -->
          <WeatherIcon :code="day.weather_code" size="md" :is-day="true" />

          <!-- 天气描述 -->
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-700 truncate">{{ day.weather_text }}</p>
            <div class="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
              <span>💧{{ day.humidity }}%</span>
              <span v-if="day.pop > 0">🌧️{{ day.pop }}%</span>
              <span>🌬️{{ day.wind_speed }}m/s</span>
            </div>
          </div>

          <!-- 温度 -->
          <div class="flex items-center gap-2 shrink-0">
            <span class="text-sm text-blue-500 font-semibold w-10 text-right">
              {{ formatTemp(day.temp_min, false) }}°
            </span>
            <!-- 温度条 -->
            <div class="w-16 h-1.5 rounded-full bg-gradient-to-r from-blue-400 via-yellow-400 to-red-400 hidden sm:block" />
            <span class="text-sm text-red-500 font-semibold w-10">
              {{ formatTemp(day.temp_max, false) }}°
            </span>
          </div>

          <!-- AQI -->
          <span
            v-if="day.aqi"
            class="text-xs px-1.5 py-0.5 rounded font-medium shrink-0"
            :style="{
              backgroundColor: day.aqi <= 50 ? '#00e400' : day.aqi <= 100 ? '#ffff00' : day.aqi <= 150 ? '#ff7e00' : '#ff0000',
              color: day.aqi <= 100 ? '#333' : '#fff',
            }"
          >
            {{ day.aqi }}
          </span>
        </div>

        <div v-if="!weatherStore.daily.length" class="text-center py-8 text-gray-400">
          暂无预报数据
        </div>
      </div>
    </div>
  </div>
</template>
