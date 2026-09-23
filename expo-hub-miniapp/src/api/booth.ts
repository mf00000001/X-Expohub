import { http, type PageResult } from '@/utils/request'

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
    return http.get<PageResult<Booth>>('/booths', { params })
  },

  getById(id: number | string) {
    return http.get<Booth>(`/booths/${id}`)
  },

  create(data: Partial<Booth>) {
    return http.post<Booth>('/booths', data as Record<string, unknown>)
  },

  update(id: number | string, data: Partial<Booth>) {
    return http.put<Booth>(`/booths/${id}`, data as Record<string, unknown>)
  },

  delete(id: number | string) {
    return http.delete<{ success?: boolean }>(`/booths/${id}`)
  },

  apply(boothId: number | string) {
    return http.post<{ success?: boolean }>(`/booths/${boothId}/apply`)
  },

  getMyBooths(params?: { page?: number; page_size?: number }) {
    return http.get<PageResult<Booth>>('/booths/my', { params })
  },

  /** 预订展位（POST /booths/book，body {booth_id}） */
  book(boothId: number | string) {
    return http.post<{ success?: boolean }>('/booths/book', { booth_id: Number(boothId) })
  },

  /** 分配展位给展商（POST /booths/{booth_id}/assign，body {exhibitor_id}，主办方） */
  assign(boothId: number | string, data: { exhibitor_id: number }) {
    return http.post<{ success?: boolean }>(`/booths/${boothId}/assign`, data)
  },
}
