import { watch, toRef } from 'vue'
import { useWeatherStore } from '@/stores/weather'
import type { MaybeRef } from 'vue'

export function useWeather(cityId: MaybeRef<number>) {
  const weatherStore = useWeatherStore()
  const cityIdRef = toRef(cityId)

  // 当 cityId 变化时自动拉取
  watch(
    cityIdRef,
    (id) => {
      if (id) {
        weatherStore.fetchFull(id)
      }
    },
    { immediate: true }
  )

  return {
    current: weatherStore.current,
    hourly: weatherStore.hourly,
    daily: weatherStore.daily,
    aqi: weatherStore.aqi,
    loading: weatherStore.loading,
    error: weatherStore.error,
    isLoading: weatherStore.isLoading,
    hasError: weatherStore.hasError,
    hasData: weatherStore.hasData,
    refetch: () => {
      if (cityIdRef.value) {
        weatherStore.fetchFull(cityIdRef.value)
      }
    },
    clear: weatherStore.clear,
  }
}
