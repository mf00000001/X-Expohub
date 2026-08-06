import http from './index'

export interface MicroBooth {
  id: number; exhibitor_id: number; name: string; description?: string
  logo_url?: string; industry_domain?: string; membership_tier: string
  product_limit: number; product_count: number
  view_count: number; search_appearances: number; favorite_count: number
  status: string; created_at?: string; updated_at?: string
}

export interface MicroBoothDetail {
  booth: MicroBooth; products: any[]
}

export const microBoothApi = {
  getList(params?: any) { return http.get('/micro-booths', { params }) },
  getMy() { return http.get('/micro-booths/my') as Promise<MicroBooth[]> },
  getDetail(id: number) { return http.get(`/micro-booths/${id}`) as Promise<MicroBoothDetail> },
  create(data: any) { return http.post('/micro-booths', data) as Promise<{ data: MicroBooth }> },
  update(id: number, data: any) { return http.put(`/micro-booths/${id}`, data) as Promise<{ data: MicroBooth }> },
  addProduct(id: number, productId: number) { return http.post(`/micro-booths/${id}/products`, { product_id: productId }) },
  removeProduct(id: number, productId: number) { return http.delete(`/micro-booths/${id}/products/${productId}`) },
  upgrade(id: number, tier: string) { return http.post(`/micro-booths/${id}/upgrade`, { tier }) },
}
