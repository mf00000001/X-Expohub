import api from './index'
import type { ApiResponse, AuthData } from '@/types/api'

export async function register(data: {
  username: string
  email: string
  password: string
}): Promise<AuthData> {
  const res = await api.post<ApiResponse<AuthData>>('/auth/register', data)
  return res.data.data
}

export async function login(data: {
  username: string
  password: string
}): Promise<AuthData> {
  const res = await api.post<ApiResponse<AuthData>>('/auth/login', data)
  return res.data.data
}
