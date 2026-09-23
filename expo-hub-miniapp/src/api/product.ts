import { http, type PageResult } from '@/utils/request'

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
    return http.get<PageResult<Product>>('/products', { params })
  },

  getById(id: number | string) {
    return http.get<Product>(`/products/${id}`)
  },

  create(data: Partial<Product>) {
    return http.post<Product>('/products', data as Record<string, unknown>)
  },

  update(id: number | string, data: Partial<Product>) {
    return http.put<Product>(`/products/${id}`, data as Record<string, unknown>)
  },

  delete(id: number | string) {
    return http.delete<{ success?: boolean }>(`/products/${id}`)
  },

  getMyProducts(params?: { page?: number; page_size?: number }) {
    return http.get<PageResult<Product>>('/products/my', { params })
  },
}
