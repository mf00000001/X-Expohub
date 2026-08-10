import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { CurrentWeather, HourlyForecast, DailyForecast, FullWeatherData, AqiDetail } from '@/types/weather'
import * as weatherApi from '@/api/weather'

export const useWeatherStore = defineStore('weather', () => {
  const current = ref<CurrentWeather | null>(null)
  const hourly = ref<HourlyForecast[]>([])
  const daily = ref<DailyForecast[]>([])
  const aqi = ref<AqiDetail | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentCityId = ref<number | null>(null)

  const isLoading = computed(() => loading.value)
  const hasError = computed(() => error.value !== null)
  const hasData = computed(() => current.value !== null)

  async function fetchFull(cityId: number) {
    loading.value = true
    error.value = null
    currentCityId.value = cityId
    try {
      const data: FullWeatherData = await weatherApi.getFull(cityId)
      current.value = data.current
      hourly.value = data.hourly || []
      daily.value = data.daily || []
      aqi.value = data.aqi || null
    } catch (e: any) {
      error.value = e.message || '获取天气数据失败'
      current.value = null
      hourly.value = []
      daily.value = []
      aqi.value = null
    } finally {
      loading.value = false
    }
  }

  async function fetchCurrent(cityId: number) {
    try {
      current.value = await weatherApi.getCurrent(cityId)
      currentCityId.value = cityId
    } catch (e: any) {
      error.value = e.message
    }
  }

  async function fetchHourly(cityId: number) {
    try {
      hourly.value = await weatherApi.getHourly(cityId)
    } catch (e: any) {
      error.value = e.message
    }
  }

  async function fetchDaily(cityId: number, days: number = 7) {
    try {
      daily.value = await weatherApi.getDaily(cityId, days)
    } catch (e: any) {
      error.value = e.message
    }
  }

  function clear() {
    current.value = null
    hourly.value = []
    daily.value = []
    aqi.value = null
    error.value = null
    currentCityId.value = null
  }

  return {
    current,
    hourly,
    daily,
    aqi,
    loading,
    error,
    currentCityId,
    isLoading,
    hasError,
    hasData,
    fetchFull,
    fetchCurrent,
    fetchHourly,
    fetchDaily,
    clear,
  }
})
