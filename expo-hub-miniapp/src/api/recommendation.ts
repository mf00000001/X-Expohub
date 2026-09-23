import { http } from '@/utils/request'

/** 推荐给展商的采购需求（GET /recommendations/for-exhibitor，含匹配度评分与原因） */
export interface ProcurementRecommendation {
  id: number
  title: string
  description?: string
  category?: string
  budget_max?: number
  status?: string
  purchaser_name?: string
  score?: number
  reasons?: string[]
  created_at?: string
}

export const recommendationApi = {
  /** 展商采购匹配推荐 */
  forExhibitor(limit = 20) {
    return http.get<ProcurementRecommendation[]>('/recommendations/for-exhibitor', {
      params: { limit },
    })
  },
}
