<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWeatherStore } from '@/stores/weather'
import { formatTemp, formatWindSpeed, formatVisibility, formatTime } from '@/utils/format'
import { getWindLevel } from '@/utils/constants'
import Loading from '@/components/common/Loading.vue'
import ErrorRetry from '@/components/common/ErrorRetry.vue'
import WeatherIcon from '@/components/weather/WeatherIcon.vue'
import AqiBadge from '@/components/weather/AqiBadge.vue'

const route = useRoute()
const router = useRouter()
const weatherStore = useWeatherStore()
const cityId = Number(route.params.id)

onMounted(() => {
  if (cityId) {
    weatherStore.fetchFull(cityId)
  }
})

const activeTab = ref<'current' | 'hourly' | 'daily'>('current')
</script>

<template>
  <div class="space-y-5 animate-fade-in">
    <!-- 返回 -->
    <button @click="router.back()" class="btn-secondary text-sm !px-3 !py-1.5">
      ← 返回
    </button>

    <Loading v-if="weatherStore.loading && !weatherStore.current" :rows="2" />
    <ErrorRetry
      v-else-if="weatherStore.error && !weatherStore.current"
      :message="weatherStore.error"
      @retry="weatherStore.fetchFull(cityId)"
    />

    <template v-else-if="weatherStore.current">
      <!-- 城市标题 -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-800">
            {{ weatherStore.current.city_name }}
          </h1>
          <p class="text-sm text-gray-500">{{ weatherStore.current.country }}</p>
        </div>
        <AqiBadge :aqi="weatherStore.current.aqi" :level="weatherStore.current.aqi_level" size="md" />
      </div>

      <!-- Tab 切换 -->
      <div class="flex gap-1 bg-gray-100 rounded-xl p-1">
        <button
          v-for="tab in (['current', 'hourly', 'daily'] as const)"
          :key="tab"
          @click="activeTab = tab"
          class="flex-1 py-2 rounded-lg text-sm font-medium transition-all"
          :class="activeTab === tab ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500'"
        >
          {{ tab === 'current' ? '当前' : tab === 'hourly' ? '逐小时' : '7日' }}
        </button>
      </div>

      <!-- 当前详情 -->
      <div v-if="activeTab === 'current'" class="card space-y-4">
        <div class="flex items-center gap-4">
          <WeatherIcon :code="weatherStore.current.weather_code" size="xl" :is-day="weatherStore.current.is_day" />
          <div>
            <div class="text-5xl font-bold text-gray-900">
              {{ formatTemp(weatherStore.current.temperature) }}
            </div>
            <p class="text-gray-500 mt-1">{{ weatherStore.current.weather_text }}</p>
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4 border-t border-gray-100">
          <div class="p-3 bg-gray-50 rounded-xl">
            <p class="text-xs text-gray-400">体感温度</p>
            <p class="text-lg font-semibold">{{ formatTemp(weatherStore.current.feels_like) }}</p>
          </div>
          <div class="p-3 bg-gray-50 rounded-xl">
            <p class="text-xs text-gray-400">湿度</p>
            <p class="text-lg font-semibold">{{ weatherStore.current.humidity }}%</p>
          </div>
          <div class="p-3 bg-gray-50 rounded-xl">
            <p class="text-xs text-gray-400">气压</p>
            <p class="text-lg font-semibold">{{ weatherStore.current.pressure }} hPa</p>
          </div>
          <div class="p-3 bg-gray-50 rounded-xl">
            <p class="text-xs text-gray-400">风速</p>
            <p class="text-lg font-semibold">{{ formatWindSpeed(weatherStore.current.wind_speed) }}</p>
          </div>
          <div class="p-3 bg-gray-50 rounded-xl">
            <p class="text-xs text-gray-400">风向</p>
            <p class="text-lg font-semibold">{{ weatherStore.current.wind_direction_text }}</p>
          </div>
          <div class="p-3 bg-gray-50 rounded-xl">
            <p class="text-xs text-gray-400">能见度</p>
            <p class="text-lg font-semibold">{{ formatVisibility(weatherStore.current.visibility) }}</p>
          </div>
          <div class="p-3 bg-gray-50 rounded-xl">
            <p class="text-xs text-gray-400">UV 指数</p>
            <p class="text-lg font-semibold">{{ weatherStore.current.uv_index }}</p>
          </div>
          <div class="p-3 bg-gray-50 rounded-xl">
            <p class="text-xs text-gray-400">观测时间</p>
            <p class="text-sm font-semibold">{{ formatTime(weatherStore.current.observation_time) }}</p>
          </div>
        </div>
      </div>

      <!-- 逐小时 -->
      <div v-if="activeTab === 'hourly'" class="card">
        <div class="space-y-3">
          <div
            v-for="h in weatherStore.hourly"
            :key="h.time"
            class="flex items-center gap-3 p-2 rounded-xl hover:bg-gray-50"
          >
            <span class="w-14 text-sm text-gray-600">{{ formatTime(h.time) }}</span>
            <WeatherIcon :code="h.weather_code" size="sm" :is-day="h.is_day" />
            <span class="flex-1 text-sm text-gray-600">{{ h.weather_text }}</span>
            <span class="font-semibold text-gray-800">{{ formatTemp(h.temperature) }}</span>
            <span class="text-xs text-gray-400 w-16 text-right">💧{{ h.humidity }}%</span>
          </div>
        </div>
      </div>

      <!-- 7日预报 -->
      <div v-if="activeTab === 'daily'" class="card">
        <div class="space-y-3">
          <div
            v-for="day in weatherStore.daily.slice(0, 7)"
            :key="day.date"
            class="flex items-center gap-3 p-2 rounded-xl hover:bg-gray-50"
          >
            <span class="w-20 text-sm text-gray-600">{{ day.date }}</span>
            <WeatherIcon :code="day.weather_code" size="sm" :is-day="true" />
            <span class="flex-1 text-sm text-gray-600">{{ day.weather_text }}</span>
            <span class="text-sm text-blue-500 w-10 text-right">{{ formatTemp(day.temp_min, false) }}°</span>
            <span class="text-sm text-red-500 w-10">{{ formatTemp(day.temp_max, false) }}°</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
