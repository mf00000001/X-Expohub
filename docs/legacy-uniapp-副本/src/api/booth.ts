import http from './index'

export interface Booth {
  id: number
  exhibition_id: number
  booth_number: string
  exhibitor_id?: number
  exhibitor_name?: string
  company_name?: string
  size?: string
  location_area?: string
  price?: number
  status: string
  description?: string
  created_at?: string
  updated_at?: string
}

export const boothApi = {
  getList(params?: { exhibition_id?: number; page?: number; page_size?: number; status?: string }) {
    return http.get('/booths', { params }).then((r) => r.data)
  },

  getById(id: number | string) {
    return http.get(`/booths/${id}`).then((r) => r.data)
  },

  create(data: Partial<Booth>) {
    return http.post('/booths', data).then((r) => r.data)
  },

  update(id: number | string, data: Partial<Booth>) {
    return http.put(`/booths/${id}`, data).then((r) => r.data)
  },

  delete(id: number | string) {
    return http.delete(`/booths/${id}`).then((r) => r.data)
  },

  apply(boothId: number | string) {
    return http.post(`/booths/${boothId}/apply`).then((r) => r.data)
  },

  getMyBooths(params?: { page?: number; page_size?: number }) {
    return http.get('/booths/my', { params }).then((r) => r.data)
  },
}
