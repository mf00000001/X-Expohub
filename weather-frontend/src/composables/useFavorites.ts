import { ref, computed } from 'vue'
import * as favoritesApi from '@/api/favorites'
import type { FavoriteItem } from '@/api/favorites'

export function useFavorites() {
  const favorites = ref<FavoriteItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const count = computed(() => favorites.value.length)
  const favoriteCityIds = computed(() => favorites.value.map((f) => f.city_id))

  function isFavorite(cityId: number): boolean {
    return favoriteCityIds.value.includes(cityId)
  }

  async function fetchFavorites() {
    loading.value = true
    error.value = null
    try {
      favorites.value = await favoritesApi.getFavorites()
    } catch (e: any) {
      error.value = e.message || '获取收藏失败'
    } finally {
      loading.value = false
    }
  }

  async function add(cityId: number) {
    try {
      const fav = await favoritesApi.addFavorite(cityId)
      favorites.value.push(fav)
    } catch (e: any) {
      error.value = e.message || '添加收藏失败'
      throw e
    }
  }

  async function remove(favoriteId: number) {
    try {
      await favoritesApi.removeFavorite(favoriteId)
      favorites.value = favorites.value.filter((f) => f.id !== favoriteId)
    } catch (e: any) {
      error.value = e.message || '移除收藏失败'
      throw e
    }
  }

  async function reorder(ids: number[]) {
    try {
      await favoritesApi.sortFavorites(ids)
      const idOrder = new Map(ids.map((id, i) => [id, i]))
      favorites.value.sort(
        (a, b) => (idOrder.get(a.id) ?? 0) - (idOrder.get(b.id) ?? 0)
      )
    } catch (e: any) {
      error.value = e.message || '排序失败'
      throw e
    }
  }

  return {
    favorites,
    loading,
    error,
    count,
    favoriteCityIds,
    isFavorite,
    fetchFavorites,
    add,
    remove,
    reorder,
  }
}
