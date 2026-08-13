import http from './index'
import type { ProductItem } from '@/api/product'

export interface ProcurementItem {
  id: number
  visitor_id: number
  visitor_username?: string
  title: string
  description?: string
  category: string
  budget_min?: number
  budget_max?: number
  deadline?: string
  status: string
  match_count: number
  created_at: string
  updated_at: string
}

export interface ProcurementMatch {
  id: number
  procurement_id: number
  exhibitor_id: number
  exhibitor_username?: string
  exhibitor_company?: string
  message?: string
  quoted_price?: number
  is_accepted?: boolean
  created_at: string
}

export interface CreateProcurementParams {
  title: string
  description?: string
  category: string
  budget_min?: number
  budget_max?: number
  deadline?: string
}

// Recommended product from procurement matching
export interface MatchProductItem extends ProductItem {
  match_score?: number
  match_reasons?: string[]
}

export const procurementApi = {
  getList(params?: { category?: string; status?: string; keyword?: string; search?: string; page?: number; page_size?: number }): Promise<ProcurementItem[]> {
    return http.get('/procurements', { params })
  },
  getDetail(id: number): Promise<ProcurementItem> {
    return http.get(`/procurements/${id}`)
  },
  create(data: CreateProcurementParams): Promise<ProcurementItem> {
    return http.post('/procurements', data)
  },
  update(id: number, data: Partial<CreateProcurementParams>): Promise<ProcurementItem> {
    return http.put(`/procurements/${id}`, data)
  },
  cancel(id: number): Promise<ProcurementItem> {
    return http.post(`/procurements/${id}/cancel`)
  },
  // 匹配相关
  getMatches(procurementId: number): Promise<ProcurementMatch[]> {
    return http.get(`/procurements/${procurementId}/matches`)
  },
  createMatch(procurementId: number, data: { message?: string; quoted_price?: number }): Promise<ProcurementMatch> {
    return http.post(`/procurements/${procurementId}/matches`, data)
  },
  acceptMatch(procurementId: number, matchId: number): Promise<ProcurementMatch> {
    return http.post(`/procurements/${procurementId}/matches/${matchId}/accept`)
  },
  // 游客自己的采购需求
  getMyProcurements(params?: { status?: string; page?: number; page_size?: number }): Promise<ProcurementItem[]> {
    return http.get('/procurements/my', { params })
  },
  getRecommendations(id: number): Promise<MatchProductItem[]> {
    return http.get('/procurements/' + id + '/recommendations')
  }
}

// Type alias for views that import `type Procurement`
export type Procurement = ProcurementItem
