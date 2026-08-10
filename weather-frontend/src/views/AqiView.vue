<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWeatherStore } from '@/stores/weather'
import { AQI_LEVEL_MAP } from '@/utils/constants'
import Loading from '@/components/common/Loading.vue'
import ErrorRetry from '@/components/common/ErrorRetry.vue'

const route = useRoute()
const router = useRouter()
const weatherStore = useWeatherStore()
const cityId = Number(route.params.id)

onMounted(() => {
  if (cityId) {
    weatherStore.fetchFull(cityId)
  }
})

function getLevelInfo(level: string) {
  return AQI_LEVEL_MAP[level] || AQI_LEVEL_MAP.good
}

function getPercent(value: number, max: number): string {
  return Math.min((value / max) * 100, 100) + '%'
}
</script>

<template>
  <div class="space-y-5 animate-fade-in">
    <button @click="router.back()" class="btn-secondary text-sm !px-3 !py-1.5">
      ← 返回
    </button>

    <h1 class="text-xl font-bold text-gray-800">
      🌬️ 空气质量
      <span v-if="weatherStore.current" class="text-base font-normal text-gray-500 ml-2">
        - {{ weatherStore.current.city_name }}
      </span>
    </h1>

    <Loading v-if="weatherStore.loading && !weatherStore.aqi" :rows="2" />
    <ErrorRetry
      v-else-if="weatherStore.error && !weatherStore.aqi"
      :message="weatherStore.error"
      @retry="weatherStore.fetchFull(cityId)"
    />

    <!-- AQI 概览 -->
    <div v-if="weatherStore.aqi || weatherStore.current?.aqi" class="card text-center">
      <div
        class="inline-flex flex-col items-center px-8 py-6 rounded-2xl"
        :style="{
          backgroundColor: (getLevelInfo(weatherStore.aqi?.level || weatherStore.current?.aqi_level || 'good')).color,
          color: (weatherStore.aqi?.level || weatherStore.current?.aqi_level) === 'moderate' ? '#333' : '#fff',
        }"
      >
        <span class="text-sm font-medium opacity-80">AQI 指数</span>
        <span class="text-6xl font-bold my-2">
          {{ weatherStore.aqi?.aqi ?? weatherStore.current?.aqi ?? '-' }}
        </span>
        <span class="text-lg font-semibold">
          {{ getLevelInfo(weatherStore.aqi?.level || weatherStore.current?.aqi_level || 'good').label }}
        </span>
        <span
          v-if="weatherStore.aqi?.primary_pollutant"
          class="text-xs mt-1 opacity-75"
        >
          首要污染物：{{ weatherStore.aqi.primary_pollutant }}
        </span>
      </div>
    </div>

    <!-- 各污染物详情 -->
    <div v-if="weatherStore.aqi" class="card space-y-4">
      <h3 class="text-base font-semibold text-gray-700">污染物详情</h3>

      <div class="space-y-3">
        <!-- PM2.5 -->
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span>PM2.5</span>
            <span class="font-semibold">{{ weatherStore.aqi.pm2_5 }} µg/m³</span>
          </div>
          <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full bg-yellow-400 transition-all"
              :style="{ width: getPercent(weatherStore.aqi.pm2_5, 500) }"
            />
          </div>
        </div>

        <!-- PM10 -->
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span>PM10</span>
            <span class="font-semibold">{{ weatherStore.aqi.pm10 }} µg/m³</span>
          </div>
          <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full bg-orange-400 transition-all"
              :style="{ width: getPercent(weatherStore.aqi.pm10, 600) }"
            />
          </div>
        </div>

        <!-- O3 -->
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span>O₃ (臭氧)</span>
            <span class="font-semibold">{{ weatherStore.aqi.o3 }} µg/m³</span>
          </div>
          <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full bg-blue-400 transition-all"
              :style="{ width: getPercent(weatherStore.aqi.o3, 800) }"
            />
          </div>
        </div>

        <!-- NO2 -->
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span>NO₂ (二氧化氮)</span>
            <span class="font-semibold">{{ weatherStore.aqi.no2 }} µg/m³</span>
          </div>
          <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full bg-purple-400 transition-all"
              :style="{ width: getPercent(weatherStore.aqi.no2, 400) }"
            />
          </div>
        </div>

        <!-- SO2 -->
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span>SO₂ (二氧化硫)</span>
            <span class="font-semibold">{{ weatherStore.aqi.so2 }} µg/m³</span>
          </div>
          <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full bg-red-400 transition-all"
              :style="{ width: getPercent(weatherStore.aqi.so2, 800) }"
            />
          </div>
        </div>

        <!-- CO -->
        <div>
          <div class="flex justify-between text-sm mb-1">
            <span>CO (一氧化碳)</span>
            <span class="font-semibold">{{ weatherStore.aqi.co }} µg/m³</span>
          </div>
          <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full bg-gray-500 transition-all"
              :style="{ width: getPercent(weatherStore.aqi.co, 50000) }"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 无 AQI 数据 -->
    <div v-if="!weatherStore.aqi && !weatherStore.loading && !weatherStore.error" class="card text-center py-8 text-gray-400">
      该城市暂无空气质量数据
    </div>
  </div>
</template>
