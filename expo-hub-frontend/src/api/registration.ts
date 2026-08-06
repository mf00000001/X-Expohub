import http from './index'
import type { ExhibitionItem } from './exhibition'

export interface RegistrationItem {
  id: number
  visitor_id: number
  exhibition_id: number
  is_favorite: boolean
  is_registered: boolean
  ticket_code?: string
  check_in_at?: string
  created_at: string
  exhibition?: ExhibitionItem
}

export interface PaginatedResponse<T> {
  list: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export const registrationApi = {
  register(data: { exhibition_id: number; is_favorite?: boolean; is_registered?: boolean }): Promise<RegistrationItem> {
    return http.post('/registrations', data)
  },

  async getMyRegistrations(params?: { page?: number; page_size?: number }): Promise<PaginatedResponse<RegistrationItem>> {
    const res = await http.get('/registrations/my', { params })
    // Backend returns { list, total, page, pageSize, totalPages }
    // If backend returns flat array (legacy), wrap it
    if (Array.isArray(res)) {
      return { list: res, total: res.length, page: 1, pageSize: res.length, totalPages: 1 }
    }
    return {
      list: res.list || res.items || res.results || [],
      total: res.total || 0,
      page: res.page || 1,
      pageSize: res.pageSize || res.list?.length || 20,
      totalPages: res.totalPages || res.total_pages || 1,
    }
  },

  cancel(exhibitionId: number): Promise<void> {
    return http.delete(`/registrations/${exhibitionId}`)
  },

  // 获取展会报名列表（通过 exhibitions 端点，主办方视角）
  async getList(params?: { exhibition_id?: number; page?: number; page_size?: number }): Promise<PaginatedResponse<RegistrationItem>> {
    const res = await http.get('/exhibitions/registrations', { params })
    if (Array.isArray(res)) {
      return { list: res, total: res.length, page: 1, pageSize: res.length, totalPages: 1 }
    }
    return {
      list: res.list || res.items || res.results || [],
      total: res.total || 0,
      page: res.page || 1,
      pageSize: res.pageSize || res.list?.length || 20,
      totalPages: res.totalPages || res.total_pages || 1,
    }
  }
}

export type Registration = RegistrationItem
