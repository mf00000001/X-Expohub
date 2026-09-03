import http from './index'
import type { Exhibition } from './exhibition'
import type { ListResp } from './paged'
import { normList } from './paged'

export interface RegistrationItem {
  id: number
  visitor_id: number
  exhibition_id: number
  is_favorite: boolean
  is_registered: boolean
  ticket_code?: string
  check_in_at?: string
  created_at: string
  // 主办方报名管理端点附带的访客信息（后端 join users 填充）
  username?: string
  email?: string
  exhibition?: Exhibition | null
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
    return http.post('/registrations', data) as Promise<RegistrationItem>
  },

  async getMyRegistrations(params?: { page?: number; page_size?: number }): Promise<ListResp<RegistrationItem>> {
    const res: any = await http.get('/registrations/my', { params })
    return normList<RegistrationItem>(res)
  },

  cancel(exhibitionId: number): Promise<void> {
    return http.delete(`/registrations/${exhibitionId}`) as Promise<void>
  },

  // 主办方/管理员查看某展会的报名列表（后端 GET /registrations?exhibition_id=）
  async getList(params?: { exhibition_id?: number; page?: number; page_size?: number }): Promise<ListResp<RegistrationItem>> {
    const res: any = await http.get('/registrations', { params })
    return normList<RegistrationItem>(res)
  },
}

export type Registration = RegistrationItem
