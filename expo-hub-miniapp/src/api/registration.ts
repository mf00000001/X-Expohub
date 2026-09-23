import { http, type PageResult } from '@/utils/request'

export interface Registration {
  id: number
  visitor_id?: number
  exhibition_id: number
  is_favorite?: boolean
  is_registered?: boolean
  ticket_code?: string
  check_in_at?: string
  username?: string
  email?: string
  created_at?: string
  exhibition?: {
    id: number
    title: string
    description?: string
    cover_image?: string
    start_date?: string
    end_date?: string
    location?: string
    status?: string
    organizer_name?: string
  }
}

export const registrationApi = {
  /** 我的报名列表 */
  getMy(params?: { page?: number; page_size?: number }) {
    return http.get<PageResult<Registration>>('/registrations/my', { params })
  },

  /** 主办方查看某展会报名列表（GET /registrations?exhibition_id=，仅主办方本人/admin） */
  getByExhibition(exhibitionId: number | string, params?: { page?: number; page_size?: number }) {
    return http.get<PageResult<Registration>>('/registrations', {
      params: { exhibition_id: exhibitionId, ...params },
    })
  },

  /** 报名展会（真实写入 registrations 表） */
  create(data: { exhibition_id: number; is_favorite?: boolean; is_registered?: boolean }) {
    return http.post<Registration>('/registrations', data)
  },

  /** 取消报名 */
  cancel(exhibitionId: number | string) {
    return http.delete<{ success?: boolean }>(`/registrations/${exhibitionId}`)
  },
}
