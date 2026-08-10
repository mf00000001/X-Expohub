import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { CitySearchResult, HotCity } from '@/types/city'
import * as citiesApi from '@/api/cities'

export const useCitiesStore = defineStore('cities', () => {
  const searchResults = ref<CitySearchResult[]>([])
  const hotCities = ref<HotCity[]>([])
  const searching = ref(false)
  const searchError = ref<string | null>(null)

  const hasResults = computed(() => searchResults.value.length > 0)

  async function search(query: string) {
    if (!query.trim()) {
      searchResults.value = []
      return
    }
    searching.value = true
    searchError.value = null
    try {
      searchResults.value = await citiesApi.searchCities(query)
    } catch (e: any) {
      searchError.value = e.message || '搜索失败'
      searchResults.value = []
    } finally {
      searching.value = false
    }
  }

  async function fetchHotCities() {
    try {
      hotCities.value = await citiesApi.getHotCities()
    } catch (e: any) {
      searchError.value = e.message
    }
  }

  function clearSearch() {
    searchResults.value = []
    searchError.value = null
  }

  return {
    searchResults,
    hotCities,
    searching,
    searchError,
    hasResults,
    search,
    fetchHotCities,
    clearSearch,
  }
})
