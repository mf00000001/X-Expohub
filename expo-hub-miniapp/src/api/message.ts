import { http, type PageResult } from '@/utils/request'

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
    return http.get<PageResult<Conversation>>('/messages/conversations', { params })
  },

  getConversation(conversationId: number | string) {
    return http.get<Conversation>(`/messages/conversations/${conversationId}`)
  },

  getMessages(conversationId: number | string, params?: { page?: number; page_size?: number }) {
    return http.get<PageResult<Message>>(`/messages/conversations/${conversationId}/messages`, { params })
  },

  sendMessage(conversationId: number | string, content: string) {
    return http.post<Message>(`/messages/conversations/${conversationId}/messages`, { content })
  },

  startConversation(receiverId: number, content: string) {
    return http.post<Conversation>('/messages/conversations', { receiver_id: receiverId, content })
  },

  markRead(conversationId: number | string) {
    return http.put<{ success?: boolean }>(`/messages/conversations/${conversationId}/read`)
  },

  getUnreadCount() {
    return http.get<{ count?: number }>('/messages/unread-count')
  },
}
