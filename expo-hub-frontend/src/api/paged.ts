// 分页/列表响应统一归一化：后端不同端点分别返回 {list}/{items}/裸数组，
// 此处统一为含 list/items/results/data 别名的宽松结构，让新旧视图都能安全读取。
export interface ListResp<T> {
  list: T[]
  items?: T[]
  results?: T[]
  data?: T[]
  matches?: T[]
  recommendations?: T[]
  total: number
  page?: number
  page_size?: number
  pageSize?: number
  total_pages?: number
  totalPages?: number
}

export function normList<T>(raw: any): ListResp<T> {
  let body = raw
  if (raw && typeof raw === 'object' && !Array.isArray(raw) && 'data' in raw && raw.data !== undefined) {
    body = raw.data
  }
  if (Array.isArray(body)) {
    const arr = body as T[]
    return { list: arr, items: arr, results: arr, data: arr, total: arr.length, page: 1, page_size: arr.length, pageSize: arr.length, totalPages: 1, total_pages: 1 }
  }
  const src = (body && typeof body === 'object') ? body : {}
  const arr: T[] = (src.list ?? src.items ?? src.results ?? src.data ?? src.matches ?? src.recommendations ?? []) as T[]
  return {
    list: arr, items: arr, results: arr, data: arr,
    matches: arr, recommendations: arr,
    total: src.total ?? src.count ?? arr.length,
    page: src.page ?? src.page_size ?? 1,
    page_size: src.pageSize ?? src.page_size ?? arr.length,
    pageSize: src.pageSize ?? src.page_size ?? arr.length,
    total_pages: src.totalPages ?? src.total_pages ?? 1,
    totalPages: src.totalPages ?? src.total_pages ?? 1,
  }
}
