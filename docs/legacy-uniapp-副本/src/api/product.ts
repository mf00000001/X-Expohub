import http from './index'

export interface Product {
  id: number
  booth_id?: number
  exhibitor_id?: number
  exhibitor_name?: string
  name: string
  description: string
  category?: string
  price?: number
  unit?: string
  images?: string[]
  stock?: number
  status: string
  created_at?: string
  updated_at?: string
}

export const productApi = {
  getList(params?: {
    page?: number
    page_size?: number
    booth_id?: number
    exhibition_id?: number
    category?: string
    search?: string
  }) {
    return http.get('/products', { params }).then((r) => r.data)
  },

  getById(id: number | string) {
    return http.get(`/products/${id}`).then((r) => r.data)
  },

  create(data: Partial<Product>) {
    return http.post('/products', data).then((r) => r.data)
  },

  update(id: number | string, data: Partial<Product>) {
    return http.put(`/products/${id}`, data).then((r) => r.data)
  },

  delete(id: number | string) {
    return http.delete(`/products/${id}`).then((r) => r.data)
  },

  getMyProducts(params?: { page?: number; page_size?: number }) {
    return http.get('/products/my', { params }).then((r) => r.data)
  },
}
