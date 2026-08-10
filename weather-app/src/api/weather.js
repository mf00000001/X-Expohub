const BASE_URL = '/api/v1'

async function request(url, options = {}) {
  const response = await fetch(`${BASE_URL}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `请求失败: ${response.status}`)
  }

  return response.json()
}

/**
 * 获取城市当前天气
 */
export function fetchCurrentWeather(cityId) {
  return request(`/weather/current/${cityId}`)
}

/**
 * 获取城市天气预报
 * @param {string} cityId - 城市ID
 * @param {number} days - 预报天数，默认7天
 */
export function fetchForecast(cityId, days = 7) {
  return request(`/weather/forecast/${cityId}?days=${days}`)
}

/**
 * 获取城市AQI空气质量
 */
export function fetchAQI(cityId) {
  return request(`/weather/aqi/${cityId}`)
}

/**
 * 搜索城市
 * @param {string} keyword - 搜索关键词
 */
export function searchCities(keyword) {
  return request(`/cities/search?keyword=${encodeURIComponent(keyword)}`)
}

/**
 * 获取城市列表（热门城市等）
 */
export function getCities() {
  return request('/cities')
}
