import api from './index'
import type { ApiResponse } from '@/types/api'
import type { City, CitySearchResult, HotCity } from '@/types/city'

export async function searchCities(query: string): Promise<CitySearchResult[]> {
  const res = await api.get<ApiResponse<CitySearchResult[]>>('/cities/search', {
    params: { q: query },
  })
  return res.data.data
}

export async function getHotCities(): Promise<HotCity[]> {
  const res = await api.get<ApiResponse<HotCity[]>>('/cities/hot')
  return res.data.data
}

export async function geocode(
  lat: number,
  lon: number
): Promise<CitySearchResult | null> {
  const res = await api.get<ApiResponse<CitySearchResult>>('/cities/geocode', {
    params: { lat, lon },
  })
  return res.data.data
}

export async function getCityDetail(cityId: number): Promise<City> {
  const res = await api.get<ApiResponse<City>>(`/cities/${cityId}`)
  return res.data.data
}
