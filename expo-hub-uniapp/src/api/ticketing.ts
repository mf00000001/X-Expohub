// 票务域 API（对齐 web 端 / expohub-backend P3 端点）
import { request, normList } from '@/utils/request'

export const ticketingApi = {
  listTicketTypes(exhibitionId: number): Promise<any> {
    return request({ url: `/ticketing/exhibitions/${exhibitionId}/ticket-types`, auth: false }).then(normList)
  },
  createTicketType(data: { exhibition_id: number; name: string; price_cents: number; quota: number; description?: string }): Promise<any> {
    return request({ url: '/ticketing/ticket-types', method: 'POST', data })
  },
  createOrder(data: { exhibition_id: number; ticket_type_id: number }): Promise<any> {
    return request({ url: '/ticketing/orders', method: 'POST', data })
  },
  payOrder(orderNo: string): Promise<any> {
    return request({ url: `/ticketing/orders/${orderNo}/pay`, method: 'POST', data: { method: 'mock' } })
  },
  cancelOrder(orderNo: string): Promise<any> {
    return request({ url: `/ticketing/orders/${orderNo}/cancel`, method: 'POST' })
  },
  myOrders(): Promise<any> {
    return request({ url: '/ticketing/orders/me' })
  },
  myTickets(): Promise<any> {
    return request({ url: '/ticketing/tickets/me' })
  },
  verifyTicket(ticketNo: string, signature: string): Promise<any> {
    return request({ url: `/ticketing/tickets/${ticketNo}/verify?signature=${encodeURIComponent(signature)}`, auth: false })
  },
}
