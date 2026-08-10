import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as weatherAPI from '../api/weather'
import * as favoritesAPI from '../api/favorites'

export const useWeatherStore = defineStore('weather', () => {
  // ---- 状态 ----
  const currentWeather = ref(null)
  const forecast = ref(null)
  const aqi = ref(null)
  const favorites = ref([])
  const loading = ref(false)
  const error = ref(null)
  const searchResults = ref([])
  const searchLoading = ref(false)

  // ---- 计算属性 ----
  const isFavorite = (cityId) => {
    return computed(() => {
      return favorites.value.some(fav => fav.city_id === cityId || fav.id === cityId)
    })
  }

  const favoriteCities = computed(() => {
    return favorites.value.map(fav => ({
      ...fav,
      city_id: fav.city_id || fav.id
    }))
  })

  // ---- 方法 ----
  /**
   * 加载城市当前天气
   */
  async function loadCurrentWeather(cityId) {
    loading.value = true
    error.value = null
    try {
      const data = await weatherAPI.fetchCurrentWeather(cityId)
      currentWeather.value = data
      return data
    } catch (err) {
      error.value = err.message
      currentWeather.value = null
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载天气预报
   */
  async function loadForecast(cityId, days = 7) {
    try {
      const data = await weatherAPI.fetchForecast(cityId, days)
      forecast.value = data
      return data
    } catch (err) {
      error.value = err.message
      forecast.value = null
      throw err
    }
  }

  /**
   * 加载AQI数据
   */
  async function loadAQI(cityId) {
    try {
      const data = await weatherAPI.fetchAQI(cityId)
      aqi.value = data
      return data
    } catch (err) {
      error.value = err.message
      aqi.value = null
    }
  }

  /**
   * 搜索城市
   */
  async function search(keyword) {
    if (!keyword || keyword.trim().length === 0) {
      searchResults.value = []
      return
    }
    searchLoading.value = true
    try {
      const data = await weatherAPI.searchCities(keyword.trim())
      searchResults.value = Array.isArray(data) ? data : (data.cities || [])
      return searchResults.value
    } catch (err) {
      searchResults.value = []
    } finally {
      searchLoading.value = false
    }
  }

  /**
   * 加载收藏列表
   */
  async function loadFavorites() {
    try {
      const data = await favoritesAPI.getFavorites()
      favorites.value = Array.isArray(data) ? data : (data.favorites || [])
    } catch (err) {
      favorites.value = []
    }
  }

  /**
   * 添加收藏
   */
  async function addToFavorites(cityId) {
    try {
      await favoritesAPI.addFavorite(cityId)
      await loadFavorites()
    } catch (err) {
      throw err
    }
  }

  /**
   * 移除收藏
   */
  async function removeFromFavorites(cityId) {
    try {
      await favoritesAPI.removeFavorite(cityId)
      favorites.value = favorites.value.filter(
        fav => (fav.city_id || fav.id) !== cityId
      )
    } catch (err) {
      throw err
    }
  }

  /**
   * 清除错误
   */
  function clearError() {
    error.value = null
  }

  return {
    // 状态
    currentWeather,
    forecast,
    aqi,
    favorites,
    loading,
    error,
    searchResults,
    searchLoading,
    favoriteCities,
    // 方法
    isFavorite,
    loadCurrentWeather,
    loadForecast,
    loadAQI,
    search,
    loadFavorites,
    addToFavorites,
    removeFromFavorites,
    clearError
  }
})
