// 票务域 API（P3 后端对应）
import http from './index'

export interface TicketTypeItem {
  id: number
  exhibition_id: number
  name: string
  price_cents: number
  quota: number
  description?: string
  active?: boolean
}

export interface OrderItem {
  order_no: string
  exhibition_id: number
  ticket_type_name: string
  amount_cents: number
  status: string
  pay_method?: string
  created_at?: string
  paid_at?: string
}

export interface TicketItem {
  ticket_no: string
  exhibition_id: number
  ticket_type_name: string
  qr_payload: string
}

export const ticketingApi = {
  // 票种（主办方/管理员）
  createTicketType(data: {
    exhibition_id: number
    name: string
    price_cents: number
    quota: number
    description?: string
  }): Promise<TicketTypeItem> {
    return http.post('/ticketing/ticket-types', data)
  },

  listTicketTypes(exhibitionId: number): Promise<{ list: TicketTypeItem[] }> {
    return http.get(`/ticketing/exhibitions/${exhibitionId}/ticket-types`)
  },

  // 订单
  createOrder(data: { exhibition_id: number; ticket_type_id: number }): Promise<OrderItem> {
    return http.post('/ticketing/orders', data)
  },

  payOrder(orderNo: string): Promise<{ order: OrderItem; ticket_no: string }> {
    return http.post(`/ticketing/orders/${orderNo}/pay`, { method: 'mock' })
  },

  cancelOrder(orderNo: string): Promise<OrderItem> {
    return http.post(`/ticketing/orders/${orderNo}/cancel`)
  },

  myOrders(): Promise<{ list: OrderItem[] }> {
    return http.get('/ticketing/orders/me')
  },

  // 入场券
  myTickets(): Promise<{ list: TicketItem[] }> {
    return http.get('/ticketing/tickets/me')
  },

  verify(ticketNo: string, signature: string): Promise<{ valid: boolean; status: string }> {
    return http.get(`/ticketing/tickets/${ticketNo}/verify`, { params: { signature } })
  }
}
