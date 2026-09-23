import { http, type PageResult } from '@/utils/request'

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
    return http.get<PageResult<Exhibition>>('/exhibitions', { params })
  },

  getById(id: number | string) {
    return http.get<Exhibition>(`/exhibitions/${id}`)
  },

  create(data: Partial<Exhibition>) {
    return http.post<Exhibition>('/exhibitions', data as Record<string, unknown>)
  },

  update(id: number | string, data: Partial<Exhibition>) {
    return http.put<Exhibition>(`/exhibitions/${id}`, data as Record<string, unknown>)
  },

  delete(id: number | string) {
    return http.delete<{ success?: boolean }>(`/exhibitions/${id}`)
  },

  // 报名
  register(exhibitionId: number | string) {
    return http.post<{ success?: boolean }>(`/exhibitions/${exhibitionId}/register`)
  },

  unregister(exhibitionId: number | string) {
    return http.delete<{ success?: boolean }>(`/exhibitions/${exhibitionId}/register`)
  },

  getRegistrations(params?: { page?: number; page_size?: number }) {
    return http.get<PageResult<unknown>>('/exhibitions/registrations', { params })
  },

  // 审核(主办方)
  approve(exhibitionId: number | string, data?: { approved: boolean; comment?: string }) {
    return http.post<{ success?: boolean }>(`/exhibitions/${exhibitionId}/approve`, data as Record<string, unknown>)
  },
}
