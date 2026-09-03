import http from './index'

export const authApi = {
  login(data: { username: string; password: string }) {
    return http.post('/auth/login', data).then((r) => r.data?.data || r.data)
  },

  register(data: { username: string; email: string; password: string; role?: string }) {
    return http.post('/auth/register', data).then((r) => r.data?.data || r.data)
  },

  getProfile() {
    return http.get('/auth/profile').then((r) => r.data?.data || r.data)
  },

  updateProfile(data: Record<string, unknown>) {
    return http.put('/auth/profile', data).then((r) => r.data?.data || r.data)
  },

  changePassword(data: { old_password: string; new_password: string }) {
    return http.put('/auth/password', data).then((r) => r.data?.data || r.data)
  },
}
