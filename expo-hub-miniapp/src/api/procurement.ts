import { http, type PageResult } from '@/utils/request'

export interface Procurement {
  id: number
  exhibition_id?: number
  exhibition_title?: string
  purchaser_id?: number
  purchaser_name?: string
  title: string
  description: string
  category?: string
  quantity?: number
  unit?: string
  budget?: number
  deadline?: string
  status: string
  created_at?: string
  updated_at?: string
}

export const procurementApi = {
  getList(params?: {
    page?: number
    page_size?: number
    exhibition_id?: number
    status?: string
    search?: string
  }) {
    return http.get<PageResult<Procurement>>('/procurements', { params })
  },

  getById(id: number | string) {
    return http.get<Procurement>(`/procurements/${id}`)
  },

  create(data: Partial<Procurement>) {
    return http.post<Procurement>('/procurements', data as Record<string, unknown>)
  },

  update(id: number | string, data: Partial<Procurement>) {
    return http.put<Procurement>(`/procurements/${id}`, data as Record<string, unknown>)
  },

  delete(id: number | string) {
    return http.delete<{ success?: boolean }>(`/procurements/${id}`)
  },

  getMyProcurements(params?: { page?: number; page_size?: number }) {
    return http.get<PageResult<Procurement>>('/procurements/my', { params })
  },

  // 匹配到的展商展品
  getMatches(procurementId: number | string) {
    return http.get<unknown>(`/procurements/${procurementId}/matches`)
  },

  // 展商响应某采购需求，提交报价（仅 exhibitor 角色）
  match(
    procurementId: number | string,
    data: { message?: string; quoted_price?: number; product_id?: number },
  ) {
    return http.post<{ success?: boolean }>(
      `/procurements/${procurementId}/matches`,
      data as Record<string, unknown>,
    )
  },
}
