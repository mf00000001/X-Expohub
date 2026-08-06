import http from './index'

export interface Review {
  id: number; exhibition_id?: number; booth_id?: number; reviewer_id: number
  reviewer_name?: string; target_type: string; target_id: number
  rating: number; content?: string; created_at?: string
}

export const reviewApi = {
  getList(params?: any) { return http.get('/reviews', { params }) },
  create(data: any) { return http.post('/reviews', data) },
  update(id: number, data: any) { return http.put(`/reviews/${id}`, data) },
  delete(id: number) { return http.delete(`/reviews/${id}`) },
}
