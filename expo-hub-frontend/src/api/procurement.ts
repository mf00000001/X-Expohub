import http from './index'
import type { ProductItem } from '@/api/product'
import type { ListResp } from './paged'
import { normList } from './paged'

export interface ProcurementItem {
  id: number
  visitor_id: number
  visitor_username?: string
  title: string
  description?: string
  category: string
  // 撮合平台后端刻意不暴露价格/数量（置 null）
  budget_min?: number | null
  budget_max?: number | null
  quantity?: number | null
  unit?: string | null
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
  async getList(params?: { category?: string; status?: string; keyword?: string; search?: string; page?: number; page_size?: number }): Promise<ListResp<ProcurementItem>> {
    const res: any = await http.get('/procurements', { params })
    return normList<ProcurementItem>(res)
  },
  getDetail(id: number): Promise<ProcurementItem> {
    return http.get(`/procurements/${id}`) as Promise<ProcurementItem>
  },
  create(data: CreateProcurementParams): Promise<ProcurementItem> {
    return http.post('/procurements', data) as Promise<ProcurementItem>
  },
  update(id: number, data: Partial<CreateProcurementParams>): Promise<ProcurementItem> {
    return http.put(`/procurements/${id}`, data) as Promise<ProcurementItem>
  },
  cancel(id: number): Promise<ProcurementItem> {
    return http.post(`/procurements/${id}/cancel`) as Promise<ProcurementItem>
  },
  // 匹配相关
  async getMatches(procurementId: number): Promise<ListResp<ProcurementMatch>> {
    const res: any = await http.get(`/procurements/${procurementId}/matches`)
    return normList<ProcurementMatch>(res)
  },
  createMatch(procurementId: number, data: { message?: string; quoted_price?: number }): Promise<ProcurementMatch> {
    return http.post(`/procurements/${procurementId}/matches`, data) as Promise<ProcurementMatch>
  },
  acceptMatch(procurementId: number, matchId: number): Promise<ProcurementMatch> {
    return http.post(`/procurements/${procurementId}/matches/${matchId}/accept`) as Promise<ProcurementMatch>
  },
  // 游客自己的采购需求
  async getMyProcurements(params?: { status?: string; page?: number; page_size?: number }): Promise<ListResp<ProcurementItem>> {
    const res: any = await http.get('/procurements/my', { params })
    return normList<ProcurementItem>(res)
  },
  async getRecommendations(id: number): Promise<ListResp<MatchProductItem>> {
    const res: any = await http.get('/procurements/' + id + '/recommendations')
    return normList<MatchProductItem>(res)
  }
}

// Type alias for views that import `type Procurement`
export type Procurement = ProcurementItem
