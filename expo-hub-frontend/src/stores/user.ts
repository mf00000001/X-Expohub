import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

export interface UserProfile {
  id: number
  username: string
  email: string
  role: string
  avatar?: string
  phone?: string
  company?: string
  created_at?: string
}

export const useUserStore = defineStore('user', () => {
  function loadProfile(): UserProfile | null {
  try { const raw = localStorage.getItem('expo_user_profile'); return raw ? JSON.parse(raw) : null }
  catch { return null }
}
function saveProfile(p: UserProfile | null) {
  if (p) localStorage.setItem('expo_user_profile', JSON.stringify(p))
  else localStorage.removeItem('expo_user_profile')
}
const profile = ref<UserProfile | null>(loadProfile())
  const token = ref<string | null>(localStorage.getItem('access_token'))

  const isLoggedIn = computed(() => !!token.value)
  const userRole = computed(() => profile.value?.role || '')

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    token.value = res.access_token
    localStorage.setItem('access_token', res.access_token)
    if (res.refresh_token) {
      localStorage.setItem('refresh_token', res.refresh_token)
    }
    // Use user data from login response directly (includes is_onboarded)
    if (res.user) { profile.value = res.user; saveProfile(res.user) }
    else { await fetchProfile() }
  }

  async function register(data: { username: string; email: string; password: string; role?: string }) {
    const res = await authApi.register(data)
    token.value = res.access_token
    localStorage.setItem('access_token', res.access_token)
    if (res.refresh_token) {
      localStorage.setItem('refresh_token', res.refresh_token)
    }
    await fetchProfile()
  }

  async function fetchProfile() {
    const res = await authApi.getProfile()
    profile.value = res
    saveProfile(res)
  }

  async function updateProfile(data: Partial<UserProfile>) {
    const res = await authApi.updateProfile(data)
    profile.value = res
    saveProfile(res)
  }

  async function logout() {
    // 主动退出登录:通知后端撤销令牌(登出后旧 token 立即失效)
    try {
      await authApi.logout()
    } catch {
      // 即使后端调用失败也继续本地登出
    }
    localLogout()
  }

  function localLogout() {
    // 仅本地清理(401 拦截器使用):不调后端,避免 token_version 全局失效与拦截器递归
    token.value = null
    profile.value = null
    saveProfile(null)
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  return {
    role: userRole,
    profile,
    token,
    isLoggedIn,
    userRole,
    login,
    register,
    fetchProfile,
    updateProfile,
    logout,
    localLogout,
  }
})
