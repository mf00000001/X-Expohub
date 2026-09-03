import apiClient from './client'
import type { ListResp } from './paged'
import { normList } from './paged'

const safe = <T>(p: Promise<T>, fb: T): Promise<T> => p.catch(() => fb)

// 后端消息/会话真实契约（modules/interaction/messages.py）：
// 会话 = participants[{id,username,avatar_url}] + last_message(对象) + unread_count + updated_at
export interface Participant {
  id: number
  username: string
  avatar_url?: string | null
}

export interface Message {
  id: number
  conversation_id?: number
  sender_id: number
  receiver_id?: number
  sender_name?: string
  receiver_name?: string
  title?: string | null
  content: string
  is_read: boolean
  read_at?: string | null
  created_at: string
  // 前端本地翻译缓存（不属于后端字段）
  _translated?: string | null
}

export interface Conversation {
  id: number
  participants: Participant[]
  last_message?: Message | null
  unread_count: number
  updated_at?: string
  // 兼容旧视图字段
  user_id?: number
  user_name?: string
  last_message_time?: string
}

export interface SendMessagePayload {
  receiver_id: number
  content: string
  conversation_id?: number
}

export const messageApi = {
  async getConversations(params?: any): Promise<ListResp<Conversation>> {
    const res: any = await apiClient.get('/messages/conversations', { params })
    return normList<Conversation>(res)
  },
  async getMessages(cid: number, params?: any): Promise<ListResp<Message>> {
    const res: any = await apiClient.get('/messages/conversations/' + cid + '/messages', { params })
    return normList<Message>(res)
  },
  // 兼容两种调用：sendMessage(cid, content) 走会话内发送；sendMessage(payload) 走自动建会话
  async sendMessage(cidOrPayload: number | SendMessagePayload, content?: string): Promise<Message> {
    if (typeof cidOrPayload === 'number') {
      const res: any = await apiClient.post(`/messages/conversations/${cidOrPayload}/messages`, { content: content ?? '' })
      return res
    }
    const res: any = await apiClient.post('/messages', cidOrPayload)
    return res
  },
  markAsRead(cid: number): Promise<void> {
    return apiClient.put('/messages/conversations/' + cid + '/read').catch(() => {}) as Promise<void>
  },
  // ConversationView 使用的旧名
  markRead(cid: number): Promise<void> {
    return messageApi.markAsRead(cid)
  },
  async translate(text: string, targetLang = 'en'): Promise<{ translated: string }> {
    const res: any = await apiClient.post('/messages/translate', { text, target_lang: targetLang })
    return res && typeof res === 'object' && 'translated' in res ? res : { translated: (res as any)?.data?.translated ?? text }
  },
  async getTypingStatus(cid: number): Promise<{ is_typing: boolean; user_id?: number }> {
    const res: any = await apiClient.get(`/messages/typing/${cid}`)
    return res?.is_typing !== undefined ? res : (res?.data ?? { is_typing: false })
  },
  setTyping(cid: number): Promise<any> {
    return apiClient.post(`/messages/typing/${cid}`)
  },
  getUnreadCount(): Promise<{ count: number }> {
    return safe(apiClient.get('/messages/unread-count'), { count: 0 }) as Promise<{ count: number }>
  },
  startConversation(uid: number, eid?: number): Promise<Conversation> {
    return apiClient.post('/messages/conversations', { user_id: uid, exhibition_id: eid }) as Promise<Conversation>
  },
}
