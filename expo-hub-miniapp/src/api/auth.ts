import { http, type PageResult } from '@/utils/request'

export interface UserProfile {
  id: number
  username: string
  email: string
  phone?: string
  nickname?: string
  avatar_url?: string
  role: string
  status: string
  company?: string
  position?: string
  bio?: string
  company_name?: string
  business_license?: string
  organizer_status?: string
  total_points?: number
  created_at?: string
  last_login_at?: string
}

export interface LoginResult {
  access_token: string
  refresh_token: string
  token_type: string
}

export const authApi = {
  login(data: { username: string; password: string }) {
    // skipAuth：登录 401 直接透出后端"用户名或密码错误"，不触发跳登录/清 token
    return http.post<LoginResult>('/auth/login', data, { skipAuth: true })
  },

  wechatLogin(data: { code: string; nickname?: string; avatar_url?: string }) {
    return http.post<LoginResult>('/auth/wechat', data, { skipAuth: true })
  },

  register(data: {
    username: string
    email: string
    password: string
    role?: string
    company_name?: string
    business_license?: string
  }) {
    return http.post<LoginResult>('/auth/register', data, { skipAuth: true })
  },

  getProfile() {
    return http.get<UserProfile>('/auth/profile')
  },

  updateProfile(data: Record<string, unknown>) {
    return http.put<UserProfile>('/auth/profile', data)
  },

  changePassword(data: { old_password: string; new_password: string }) {
    return http.put<{ success?: boolean }>('/auth/password', data)
  },
}

export type { PageResult }
