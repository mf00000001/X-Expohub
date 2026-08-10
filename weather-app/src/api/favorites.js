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
 * 添加收藏
 */
export function addFavorite(cityId) {
  return request('/favorites', {
    method: 'POST',
    body: JSON.stringify({ city_id: cityId })
  })
}

/**
 * 获取收藏列表
 */
export function getFavorites() {
  return request('/favorites')
}

/**
 * 取消收藏
 */
export function removeFavorite(cityId) {
  return request(`/favorites/${cityId}`, {
    method: 'DELETE'
  })
}
