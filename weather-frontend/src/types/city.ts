export interface City {
  id: number
  name: string
  country: string
  country_code: string
  state: string
  latitude: number
  longitude: number
  timezone: string
  population: number
  is_hot: boolean
}

export interface CitySearchResult {
  id: number
  name: string
  country: string
  country_code: string
  state: string
  latitude: number
  longitude: number
}

export interface HotCity {
  id: number
  name: string
  country: string
  country_code: string
}
