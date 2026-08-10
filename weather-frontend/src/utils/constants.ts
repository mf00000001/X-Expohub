/**
 * AQI 等级颜色映射
 */
export const AQI_COLORS: Record<string, string> = {
  good: '#00E400',
  moderate: '#FFFF00',
  unhealthy_sensitive: '#FF7E00',
  unhealthy: '#FF0000',
  very_unhealthy: '#99004C',
  hazardous: '#7E0023',
}

export const AQI_LEVEL_MAP: Record<string, { label: string; color: string; bg: string; text: string }> = {
  good: { label: '优', color: '#00E400', bg: 'bg-aqi-good', text: 'text-white' },
  moderate: { label: '良', color: '#FFFF00', bg: 'bg-aqi-moderate', text: 'text-gray-900' },
  unhealthy_sensitive: { label: '轻度污染', color: '#FF7E00', bg: 'bg-aqi-unhealthy1', text: 'text-white' },
  unhealthy: { label: '中度污染', color: '#FF0000', bg: 'bg-aqi-unhealthy2', text: 'text-white' },
  very_unhealthy: { label: '重度污染', color: '#8f3f97', bg: 'bg-aqi-veryUnhealthy', text: 'text-white' },
  hazardous: { label: '严重污染', color: '#7E0023', bg: 'bg-aqi-hazardous', text: 'text-white' },
}

/**
 * 天气图标 Emoji 映射
 */
export const WEATHER_ICONS: Record<string, string> = {
  sunny: '☀️',
  clear: '☀️',
  partly_cloudy: '⛅',
  cloudy: '☁️',
  overcast: '☁️',
  fog: '🌫️',
  mist: '🌫️',
  haze: '🌫️',
  drizzle: '🌧️',
  light_rain: '🌧️',
  rain: '🌧️',
  moderate_rain: '🌧️',
  heavy_rain: '🌧️',
  thunderstorm: '⛈️',
  snow: '❄️',
  light_snow: '❄️',
  heavy_snow: '❄️',
  sleet: '🌨️',
  hail: '🌨️',
  wind: '🌬️',
  rainbow: '🌈',
  tornado: '🌪️',
  hurricane: '🌀',
}

/**
 * 根据 weather_code 映射到 icon
 */
export function getWeatherEmoji(code: string): string {
  const normalized = code?.toLowerCase().replace(/[\s_]/g, '_')
  return WEATHER_ICONS[normalized] || '🌈'
}

/**
 * 风力等级（蒲福风级）
 */
export const WIND_LEVELS = [
  { level: 0, label: '无风', max: 0.2 },
  { level: 1, label: '软风', max: 1.5 },
  { level: 2, label: '轻风', max: 3.3 },
  { level: 3, label: '微风', max: 5.4 },
  { level: 4, label: '和风', max: 7.9 },
  { level: 5, label: '清风', max: 10.7 },
  { level: 6, label: '强风', max: 13.8 },
  { level: 7, label: '劲风', max: 17.1 },
  { level: 8, label: '大风', max: 20.7 },
  { level: 9, label: '烈风', max: 24.4 },
  { level: 10, label: '狂风', max: 28.4 },
  { level: 11, label: '暴风', max: 32.6 },
  { level: 12, label: '飓风', max: Infinity },
]

export function getWindLevel(speed: number) {
  return WIND_LEVELS.find((w) => speed <= w.max) || WIND_LEVELS[12]
}

/**
 * UV 指数等级
 */
export function getUvLevel(index: number): { label: string; color: string } {
  if (index <= 2) return { label: '低', color: '#00E400' }
  if (index <= 5) return { label: '中等', color: '#FFFF00' }
  if (index <= 7) return { label: '高', color: '#FF7E00' }
  if (index <= 10) return { label: '很高', color: '#FF0000' }
  return { label: '极高', color: '#99004C' }
}

/**
 * 默认城市 ID（北京）
 */
export const DEFAULT_CITY_ID = 1

/**
 * 热门城市预设
 */
export const PRESET_HOT_CITIES = [
  { id: 1, name: '北京' },
  { id: 2, name: '上海' },
  { id: 3, name: '广州' },
  { id: 4, name: '深圳' },
  { id: 6, name: '杭州' },
  { id: 8, name: '南京' },
  { id: 5, name: '成都' },
  { id: 10, name: '西安' },
]
