import { http } from '@/utils/request'

/** 展商数据总览（GET /exhibitor/analytics/overview） */
export interface ExhibitorOverview {
  today: { views: number; searches: number; favorites: number }
  total: { views: number; searches: number; favorites: number }
  products: number
  booths: number
  matches: { total: number; accepted: number }
}

export const dashboardApi = {
  /** 展商工作台统计：展位/展品/采购匹配/浏览量（仅展商/管理员可用） */
  getExhibitorOverview() {
    return http.get<ExhibitorOverview>('/exhibitor/analytics/overview')
  },
}
