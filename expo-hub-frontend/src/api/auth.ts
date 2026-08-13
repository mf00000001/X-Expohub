import http from './index'

export interface LoginParams {
  username: string
  password: string
}

export interface RegisterParams {
  username: string
  email: string
  password: string
  role: string
  nickname?: string
  phone?: string
  company?: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserProfile
}

export interface UserProfile {
  id: number
  username: string
  email: string
  phone?: string
  role: string
  status: string
  nickname?: string
  avatar_url?: string
  gender?: string
  company?: string
  position?: string
  bio?: string
  created_at: string
  last_login_at?: string
}

export const authApi = {
  login(data: LoginParams): Promise<TokenResponse> {
    return http.post('/auth/login', data)
  },
  register(data: RegisterParams): Promise<TokenResponse> {
    return http.post('/auth/register', data)
  },
  refreshToken(refreshToken: string): Promise<{ access_token: string; token_type: string; expires_in: number }> {
    return http.post('/auth/refresh', { refresh_token: refreshToken })
  },
  // V3.2: 登出(服务端撤销令牌)
  logout(): Promise<void> {
    return http.post('/auth/logout')
  },
  getMe(): Promise<UserProfile> {
    return http.get('/auth/profile')
  },
  getProfile(): Promise<UserProfile> {
    return http.get('/auth/profile')
  },
  updateProfile(data: Partial<UserProfile>): Promise<UserProfile> {
    return http.put('/auth/profile', data)
  },
  // 修改密码(后端 PUT /api/auth/password)
  changePassword(data: { old_password: string; new_password: string }) {
    return http.put('/auth/password', data)
  },
  // V2.0: 兴趣引导
  saveInterests(interests: string[]): Promise<UserProfile> {
    return http.put('/auth/interests', { interests })
  },
}
