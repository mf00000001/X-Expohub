import apiClient from './client'
const safe = <T>(p:Promise<T>,fb:T):Promise<T> => p.catch(() => fb)
export interface Message { id:number;sender_id:number;receiver_id:number;content:string;is_read:boolean;created_at:string;sender_name?:string;receiver_name?:string }
export interface Conversation { id:number;user_id:number;user_name:string;last_message:string;last_message_time:string;unread_count:number;exhibition_id?:number;exhibition_title?:string }
export interface SendMessagePayload { receiver_id:number;content:string;conversation_id?:number }
export const messageApi = {
  getConversations() { return safe(apiClient.get('/messages/conversations'),[]) as Promise<Conversation[]> },
  getMessages(cid:number,params?:any) { return safe(apiClient.get('/messages/conversations/'+cid+'/messages',{params}),{list:[],total:0}) as Promise<{list:Message[];total:number}> },
  sendMessage(p:SendMessagePayload) { return apiClient.post('/messages',p) as Promise<Message> },
  markAsRead(cid:number) { return apiClient.put('/messages/conversations/'+cid+'/read').catch(()=>{}) as Promise<void> },
  getUnreadCount() { return safe(apiClient.get('/messages/unread-count'),{count:0}) as Promise<{count:number}> },
  startConversation(uid:number,eid?:number) { return apiClient.post('/messages/conversations',{user_id:uid,exhibition_id:eid}) as Promise<Conversation> },
}
