import api from './index'
import type { ApiResponse } from '@/types/api'
import type { City } from '@/types/city'

export interface FavoriteItem {
  id: number
  user_id: number
  city_id: number
  sort_order: number
  created_at: string
  city: City
}

export async function getFavorites(): Promise<FavoriteItem[]> {
  const res = await api.get<ApiResponse<FavoriteItem[]>>('/favorites')
  return res.data.data
}

export async function addFavorite(cityId: number): Promise<FavoriteItem> {
  const res = await api.post<ApiResponse<FavoriteItem>>('/favorites', {
    city_id: cityId,
  })
  return res.data.data
}

export async function removeFavorite(favoriteId: number): Promise<void> {
  await api.delete(`/favorites/${favoriteId}`)
}

export async function sortFavorites(ids: number[]): Promise<void> {
  await api.put('/favorites/sort', { ids })
}
