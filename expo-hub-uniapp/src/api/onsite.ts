// 现场核销域 API（对齐 web 端 / expohub-backend P4 端点）
import { request } from '@/utils/request'

export const onsiteApi = {
  checkin(data: { exhibition_id: number; ticket_no: string; signature: string }): Promise<any> {
    return request({ url: '/onsite/checkin', method: 'POST', data })
  },
  batchCheckin(exhibition_id: number, items: Array<{ ticket_no: string; signature: string }>): Promise<any> {
    return request({ url: '/onsite/checkin/batch', method: 'POST', data: { exhibition_id, items } })
  },
  revoke(ticketNo: string, exhibitionId: number): Promise<any> {
    return request({ url: `/onsite/tickets/${ticketNo}/revoke?exhibition_id=${exhibitionId}`, method: 'POST' })
  },
  stats(exhibitionId: number): Promise<any> {
    return request({ url: `/onsite/exhibitions/${exhibitionId}/stats`, auth: false })
  },
}
