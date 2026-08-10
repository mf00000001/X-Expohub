<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useWeatherStore } from '@/stores/weather'
import { useCitiesStore } from '@/stores/cities'
import { useUserStore } from '@/stores/user'
import { geocode } from '@/api/cities'
import { useGeolocation } from '@/composables/useGeolocation'
import { useFavorites } from '@/composables/useFavorites'
import { DEFAULT_CITY_ID, PRESET_HOT_CITIES } from '@/utils/constants'
import WeatherCard from '@/components/weather/WeatherCard.vue'
import ForecastList from '@/components/weather/ForecastList.vue'
import HourlyChart from '@/components/weather/HourlyChart.vue'
import Loading from '@/components/common/Loading.vue'
import ErrorRetry from '@/components/common/ErrorRetry.vue'

const router = useRouter()
const weatherStore = useWeatherStore()
const citiesStore = useCitiesStore()
const userStore = useUserStore()
const { location, getPosition } = useGeolocation()
const { favorites, fetchFavorites } = useFavorites()

const activeCityId = ref<number>(DEFAULT_CITY_ID)
const locating = ref(false)

onMounted(async () => {
  await weatherStore.fetchFull(activeCityId.value)
  citiesStore.fetchHotCities()
  if (userStore.isLoggedIn) {
    fetchFavorites()
  }
})

// 定位到当前城市
async function locateMe() {
  locating.value = true
  try {
    const pos = await getPosition()
    const city = await geocode(pos.latitude, pos.longitude)
    if (city) {
      activeCityId.value = city.id
      await weatherStore.fetchFull(city.id)
    }
  } catch (e) {
    console.error('定位失败', e)
  } finally {
    locating.value = false
  }
}

// 首页展示的热门城市（收藏或预设）
const displayCities = computed(() => {
  if (favorites.value.length > 0) {
    return favorites.value.map((f) => f.city)
  }
  return PRESET_HOT_CITIES
})

function selectCity(cityId: number) {
  activeCityId.value = cityId
  weatherStore.fetchFull(cityId)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function goToDetail() {
  router.push({ name: 'city-detail', params: { id: activeCityId.value } })
}

function goToForecast() {
  router.push({ name: 'forecast', params: { id: activeCityId.value } })
}

function goToAqi() {
  router.push({ name: 'aqi', params: { id: activeCityId.value } })
}
</script>

<template>
  <div class="space-y-5 animate-fade-in">
    <!-- 定位按钮 -->
    <div class="flex items-center justify-between">
      <h1 class="text-xl sm:text-2xl font-bold text-gray-800">
        ☀️ 天气查询
      </h1>
      <button
        @click="locateMe"
        :disabled="locating"
        class="btn-secondary text-sm !px-3 !py-1.5"
      >
        <span v-if="locating" class="animate-spin mr-1">⏳</span>
        <span v-else>📍</span>
        定位
      </button>
    </div>

    <!-- 加载 / 错误 / 数据 -->
    <template v-if="weatherStore.loading && !weatherStore.current">
      <Loading :rows="2" type="card" />
      <Loading :rows="8" type="list" />
    </template>

    <ErrorRetry
      v-else-if="weatherStore.error && !weatherStore.current"
      :message="weatherStore.error"
      @retry="weatherStore.fetchFull(activeCityId)"
    />

    <template v-else-if="weatherStore.current">
      <!-- 当前天气大卡 -->
      <WeatherCard
        :weather="weatherStore.current"
        @click="goToDetail"
      />

      <!-- 操作按钮组 -->
      <div class="flex gap-2 flex-wrap">
        <button @click="goToDetail" class="btn-outline text-sm !px-3 !py-1.5">
          📊 详细数据
        </button>
        <button @click="goToForecast" class="btn-outline text-sm !px-3 !py-1.5">
          📅 15日预报
        </button>
        <button @click="goToAqi" class="btn-outline text-sm !px-3 !py-1.5">
          🌬️ 空气质量
        </button>
      </div>

      <!-- 逐小时 -->
      <HourlyChart :hourly="weatherStore.hourly" />

      <!-- 7日预报 -->
      <ForecastList
        :daily="weatherStore.daily.slice(0, 7)"
        @select="(d: string) => router.push({ name: 'forecast', params: { id: activeCityId } })"
      />
    </template>

    <!-- 热门 / 收藏城市 -->
    <div class="card">
      <h3 class="text-base font-semibold text-gray-700 mb-3">
        {{ favorites.length > 0 ? '⭐ 我的收藏' : '🔥 热门城市' }}
      </h3>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <button
          v-for="city in displayCities"
          :key="city.id"
          @click="selectCity(city.id)"
          class="p-3 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50 text-sm font-medium text-gray-700 transition-all"
          :class="{ 'ring-2 ring-blue-500 bg-blue-50': city.id === activeCityId }"
        >
          {{ city.name }}
        </button>
      </div>
    </div>
  </div>
</template>
