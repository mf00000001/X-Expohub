/**
 * 通用格式化工具函数
 */

/**
 * 格式化日期
 * @param dateStr - 日期字符串或时间戳
 * @param withTime - 是否包含时间
 */
export function formatDate(dateStr: string | number | Date, withTime = false): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const base = `${y}-${m}-${day}`
  if (withTime) {
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    return `${base} ${h}:${min}`
  }
  return base
}

/**
 * 格式化价格（人民币）
 */
export function formatPrice(price: number): string {
  if (price == null || isNaN(price)) return '¥0'
  if (price >= 10000) {
    return `¥${(price / 10000).toFixed(1)}万`
  }
  return `¥${price.toLocaleString('zh-CN')}`
}

/**
 * 格式化大数字（访问量等）
 */
export function formatNumber(num: number): string {
  if (num == null || isNaN(num)) return '0'
  if (num >= 10000) {
    return `${(num / 10000).toFixed(1)}万`
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}k`
  }
  return String(num)
}

/**
 * 相对时间（多久之前）
 */
export function relativeTime(dateStr: string | number | Date): string {
  const now = Date.now()
  const d = new Date(dateStr).getTime()
  const diff = now - d
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return '刚刚'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}个月前`
  return `${Math.floor(months / 12)}年前`
}

/**
 * 截断文本
 */
export function truncateText(text: string, maxLen: number): string {
  if (!text) return ''
  if (text.length <= maxLen) return text
  return text.slice(0, maxLen) + '...'
}
