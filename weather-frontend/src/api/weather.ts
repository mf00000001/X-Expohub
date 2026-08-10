import api from './index'
import type { ApiResponse } from '@/types/api'
import type { CurrentWeather, HourlyForecast, DailyForecast, FullWeatherData } from '@/types/weather'

export async function getCurrent(cityId: number): Promise<CurrentWeather> {
  const res = await api.get<ApiResponse<CurrentWeather>>('/weather/current', {
    params: { city_id: cityId },
  })
  return res.data.data
}

export async function getHourly(cityId: number): Promise<HourlyForecast[]> {
  const res = await api.get<ApiResponse<HourlyForecast[]>>('/weather/hourly', {
    params: { city_id: cityId },
  })
  return res.data.data
}

export async function getDaily(
  cityId: number,
  days: number = 7
): Promise<DailyForecast[]> {
  const res = await api.get<ApiResponse<DailyForecast[]>>('/weather/daily', {
    params: { city_id: cityId, days },
  })
  return res.data.data
}

export async function getFull(cityId: number): Promise<FullWeatherData> {
  const res = await api.get<ApiResponse<FullWeatherData>>('/weather/full', {
    params: { city_id: cityId },
  })
  return res.data.data
}
