import { useSettingsStore } from '@/stores/settings'

/**
 * 摄氏度转华氏度
 */
export function celsiusToFahrenheit(c: number): number {
  return Math.round((c * 9) / 5 + 32)
}

/**
 * 根据当前设置的单位格式化温度
 */
export function formatTemp(celsius: number, withUnit = true): string {
  const settings = useSettingsStore()
  if (settings.temperatureUnit === 'fahrenheit') {
    const f = celsiusToFahrenheit(celsius)
    return withUnit ? `${f}℉` : `${f}`
  }
  return withUnit ? `${Math.round(celsius)}℃` : `${Math.round(celsius)}`
}

/**
 * 格式化日期
 */
export function formatDate(dateStr: string, short = false): string {
  const date = new Date(dateStr)
  const month = date.getMonth() + 1
  const day = date.getDate()
  if (short) {
    return `${month}/${day}`
  }
  const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${month}月${day}日 ${weekDays[date.getDay()]}`
}

/**
 * 格式化时间
 */
export function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * 格式化风速
 */
export function formatWindSpeed(speed: number): string {
  return `${speed.toFixed(1)} m/s`
}

/**
 * 格式化可见度
 */
export function formatVisibility(meters: number): string {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`
  }
  return `${meters} m`
}
