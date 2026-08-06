import http from './index'
import type { UserProfile } from './auth'

export const userApi = {
  getProfile(): Promise<UserProfile> {
    return http.get('/auth/profile')
  },
  updateProfile(data: Partial<UserProfile>): Promise<UserProfile> {
    return http.put('/auth/profile', data)
  }
}
