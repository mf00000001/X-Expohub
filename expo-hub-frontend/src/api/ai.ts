// AI 原生层 API（P5 后端对应）
import http from './index'

export interface AiGenerateResult {
  provider: string
  degraded: boolean
  content: string
  usage: { cost_cents: number; month_cost_cents: number; budget_cents: number; budget_unlimited: boolean }
}

export interface AiUsageItem {
  id: number
  capability: string
  provider: string
  degraded: boolean
  prompt_chars: number
  response_chars: number
  cost_cents: number
  created_at?: string
}

export const aiApi = {
  generate(data: { capability: string; prompt: string }): Promise<AiGenerateResult> {
    return http.post('/ai/generate', data)
  },

  myUsage(): Promise<{ total_cost_cents: number; list: AiUsageItem[] }> {
    return http.get('/ai/usage/me')
  }
}
