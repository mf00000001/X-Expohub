import http from './index'
import type { ListResp } from './paged'
import { normList } from './paged'

export interface Review {
  id: number; exhibition_id?: number; booth_id?: number; reviewer_id: number
  reviewer_name?: string; target_type: string; target_id: number
  rating: number; content?: string; created_at?: string
}

export const reviewApi = {
  async getList(params?: any): Promise<ListResp<Review>> {
    const res: any = await http.get('/reviews', { params })
    return normList<Review>(res)
  },
  create(data: any) { return http.post('/reviews', data) as Promise<Review> },
  update(id: number, data: any) { return http.put(`/reviews/${id}`, data) as Promise<Review> },
  delete(id: number) { return http.delete(`/reviews/${id}`) as Promise<void> },
}
