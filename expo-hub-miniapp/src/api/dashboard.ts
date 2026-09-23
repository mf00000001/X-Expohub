import { http } from '@/utils/request'

/** 展商数据总览（GET /exhibitor/analytics/overview） */
export interface ExhibitorOverview {
  today: { views: number; searches: number; favorites: number }
  total: { views: number; searches: number; favorites: number }
  products: number
  booths: number
  matches: { total: number; accepted: number }
}

/** 平台综合统计（GET /admin/stats/overview，仅 admin/organizer） */
export interface StatsOverview {
  total_users: number
  total_exhibitions: number
  total_booths: number
  total_registrations: number
  total_procurements: number
  total_products: number
  total_messages: number
  user_role_distribution?: Record<string, number>
  exhibition_status_distribution?: Record<string, number>
  procurement_status_distribution?: Record<string, number>
  exhibitor_active_count: number
  exhibitor_with_booth_count: number
  exhibitor_with_product_count: number
  procurement_total: number
  procurement_matched: number
  procurement_match_rate: number
}

export const dashboardApi = {
  /** 展商工作台统计：展位/展品/采购匹配/浏览量（仅 exhibitor/admin/organizer 可用） */
  getExhibitorOverview() {
    return http.get<ExhibitorOverview>('/exhibitor/analytics/overview')
  },

  /** 平台综合统计（仅 admin/organizer，注意路由在 /admin 前缀下） */
  getStatsOverview() {
    return http.get<StatsOverview>('/admin/stats/overview')
  },

  /** 概览统计（旧版，仅 admin/organizer） */
  getStats() {
    return http.get<Record<string, unknown>>('/admin/stats')
  },

  /** 展会统计（GET /admin/stats/exhibitions，仅 admin/organizer） */
  getExhibitionStats() {
    return http.get<{ total: number; by_status: Record<string, number>; recent: unknown[] }>(
      '/admin/stats/exhibitions',
    )
  },

  /** 用户列表（GET /admin/users，仅 admin/organizer，可筛角色） */
  getUserList(params?: { role?: string; status?: string; page?: number }) {
    return http.get<{ list: unknown[]; total: number; page: number }>('/admin/users', { params })
  },
}
