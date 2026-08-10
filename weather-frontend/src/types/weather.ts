export interface CurrentWeather {
  temperature: number
  feels_like: number
  humidity: number
  pressure: number
  wind_speed: number
  wind_direction: number
  wind_direction_text: string
  visibility: number
  weather_code: string
  weather_text: string
  weather_icon: string
  uv_index: number
  city_id: number
  city_name: string
  country: string
  aqi: number
  aqi_level: string
  observation_time: string
  is_day: boolean
}

export interface HourlyForecast {
  time: string
  temperature: number
  weather_code: string
  weather_text: string
  weather_icon: string
  wind_speed: number
  humidity: number
  pop: number
  is_day: boolean
}

export interface DailyForecast {
  date: string
  temp_max: number
  temp_min: number
  weather_code: string
  weather_text: string
  weather_icon: string
  sunrise: string
  sunset: string
  humidity: number
  wind_speed: number
  pop: number
  uv_index: number
}

export interface AqiDetail {
  aqi: number
  level: string
  primary_pollutant: string
  pm2_5: number
  pm10: number
  o3: number
  no2: number
  so2: number
  co: number
}

export interface FullWeatherData {
  current: CurrentWeather
  hourly: HourlyForecast[]
  daily: DailyForecast[]
  aqi: AqiDetail | null
}

export interface WeatherAlert {
  id: number
  city_id: number
  title: string
  description: string
  severity: string
  start_time: string
  end_time: string
}
