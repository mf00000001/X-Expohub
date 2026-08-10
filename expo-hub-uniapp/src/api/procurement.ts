import http from './index'

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
    return http.get('/procurements', { params }).then((r) => r.data)
  },

  getById(id: number | string) {
    return http.get(`/procurements/${id}`).then((r) => r.data)
  },

  create(data: Partial<Procurement>) {
    return http.post('/procurements', data).then((r) => r.data)
  },

  update(id: number | string, data: Partial<Procurement>) {
    return http.put(`/procurements/${id}`, data).then((r) => r.data)
  },

  delete(id: number | string) {
    return http.delete(`/procurements/${id}`).then((r) => r.data)
  },

  getMyProcurements(params?: { page?: number; page_size?: number }) {
    return http.get('/procurements/my', { params }).then((r) => r.data)
  },

  // 匹配展商的展品
  getMatches(procurementId: number | string) {
    return http.get(`/procurements/${procurementId}/matches`).then((r) => r.data)
  },
}
