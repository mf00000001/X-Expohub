import http from './index'

export interface Review {
  id: number
  exhibition_id?: number
  booth_id?: number
  reviewer_id: number
  reviewer_name?: string
  target_type: string
  target_id: number
  rating: number
  content: string
  created_at: string
}

export const reviewApi = {
  getList(params?: {
    target_type?: string
    target_id?: number
    page?: number
    page_size?: number
  }) {
    return http.get('/reviews', { params }).then((r) => r.data)
  },

  create(data: {
    target_type: string
    target_id: number
    rating: number
    content: string
  }) {
    return http.post('/reviews', data).then((r) => r.data)
  },

  update(id: number | string, data: { rating?: number; content?: string }) {
    return http.put(`/reviews/${id}`, data).then((r) => r.data)
  },

  delete(id: number | string) {
    return http.delete(`/reviews/${id}`).then((r) => r.data)
  },
}
