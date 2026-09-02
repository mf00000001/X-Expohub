// 平台运营域 API（P6 后端对应）
import http from './index'

export interface PlanItem {
  id: number
  tier: string
  name: string
  monthly_fee_cents: number
  features: string[]
  active: boolean
}

export interface ImportRowResult {
  row: number
  title: string
  ok: boolean
  reason: string
}

export const platformApi = {
  plans(): Promise<{ list: PlanItem[] }> {
    return http.get('/platform/plans')
  },

  upsertPlan(data: { tier: string; name: string; monthly_fee_cents: number; features: string[] }): Promise<PlanItem> {
    return http.post('/platform/plans', data)
  },

  myPlan(): Promise<{ tenant_id: string; plan: PlanItem; usage: Record<string, number> }> {
    return http.get('/platform/me/plan')
  },

  assignPlan(tenantId: string, planId: number): Promise<{ tenant_id: string; plan: PlanItem }> {
    return http.put(`/platform/tenants/${tenantId}/plan`, { plan_id: planId })
  },

  importExhibitions(rows: unknown[]): Promise<{ success_count: number; total: number; results: ImportRowResult[] }> {
    return http.post('/platform/import/exhibitions', { rows })
  },

  overview(): Promise<Record<string, number>> {
    return http.get('/platform/overview')
  }
}
