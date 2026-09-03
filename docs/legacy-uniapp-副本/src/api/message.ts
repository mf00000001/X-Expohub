import http from './index'

export interface Message {
  id: number
  conversation_id: number
  sender_id: number
  sender_name?: string
  receiver_id: number
  content: string
  is_read: boolean
  created_at: string
}

export interface Conversation {
  id: number
  participants: Array<{ id: number; username: string; avatar?: string }>
  last_message?: Message
  unread_count: number
  updated_at: string
}

export const messageApi = {
  getConversations(params?: { page?: number; page_size?: number }) {
    return http.get('/messages/conversations', { params }).then((r) => r.data)
  },

  getConversation(conversationId: number | string) {
    return http.get(`/messages/conversations/${conversationId}`).then((r) => r.data)
  },

  getMessages(conversationId: number | string, params?: { page?: number; page_size?: number }) {
    return http.get(`/messages/conversations/${conversationId}/messages`, { params }).then((r) => r.data)
  },

  sendMessage(conversationId: number | string, content: string) {
    return http.post(`/messages/conversations/${conversationId}/messages`, { content }).then((r) => r.data)
  },

  startConversation(receiverId: number, content: string) {
    return http.post('/messages/conversations', { receiver_id: receiverId, content }).then((r) => r.data)
  },

  markRead(conversationId: number | string) {
    return http.put(`/messages/conversations/${conversationId}/read`).then((r) => r.data)
  },

  getUnreadCount() {
    return http.get('/messages/unread-count').then((r) => r.data)
  },
}
