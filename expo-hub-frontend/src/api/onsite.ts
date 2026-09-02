// 现场签到域 API（P4 后端对应）
import http from './index'

export interface CheckinResult {
  ticket_no: string
  ok: boolean
  reason: string
}

export interface OnsiteStats {
  exhibition_id: number
  checkin_count: number
  revoke_count: number
  by_ticket_type: Record<string, number>
  by_hour: { hour: string; checkin: number }[]
  latest: { ticket_no: string; action: string; ticket_type_name: string; at?: string }[]
}

export const onsiteApi = {
  checkin(data: { exhibition_id: number; ticket_no: string; signature: string }): Promise<CheckinResult> {
    return http.post('/onsite/checkin', data)
  },

  batchCheckin(data: {
    exhibition_id: number
    items: { exhibition_id: number; ticket_no: string; signature: string }[]
  }): Promise<{ success_count: number; total: number; results: CheckinResult[] }> {
    return http.post('/onsite/checkin/batch', data)
  },

  revoke(ticketNo: string, exhibitionId: number): Promise<{ ticket_no: string; status: string }> {
    return http.post(`/onsite/tickets/${ticketNo}/revoke`, null, { params: { exhibition_id: exhibitionId } })
  },

  stats(exhibitionId: number): Promise<OnsiteStats> {
    return http.get(`/onsite/exhibitions/${exhibitionId}/stats`)
  }
}
