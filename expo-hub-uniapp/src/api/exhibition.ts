import http from './index'

export interface Exhibition {
  id: number
  title: string
  description: string
  cover_image?: string
  start_date: string
  end_date: string
  location: string
  status: string
  organizer_id?: number
  organizer_name?: string
  created_at?: string
  updated_at?: string
}

export const exhibitionApi = {
  getList(params?: { page?: number; page_size?: number; status?: string; search?: string }) {
    return http.get('/exhibitions', { params }).then((r) => r.data)
  },

  getById(id: number | string) {
    return http.get(`/exhibitions/${id}`).then((r) => r.data)
  },

  create(data: Partial<Exhibition>) {
    return http.post('/exhibitions', data).then((r) => r.data)
  },

  update(id: number | string, data: Partial<Exhibition>) {
    return http.put(`/exhibitions/${id}`, data).then((r) => r.data)
  },

  delete(id: number | string) {
    return http.delete(`/exhibitions/${id}`).then((r) => r.data)
  },

  // Registration
  register(exhibitionId: number | string) {
    return http.post(`/exhibitions/${exhibitionId}/register`).then((r) => r.data)
  },

  unregister(exhibitionId: number | string) {
    return http.delete(`/exhibitions/${exhibitionId}/register`).then((r) => r.data)
  },

  getRegistrations(params?: { page?: number; page_size?: number }) {
    return http.get('/exhibitions/registrations', { params }).then((r) => r.data)
  },

  // Approval
  approve(exhibitionId: number | string, data?: { approved: boolean; comment?: string }) {
    return http.post(`/exhibitions/${exhibitionId}/approve`, data).then((r) => r.data)
  },
}
