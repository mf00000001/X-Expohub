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
  const profile = ref<UserProfile | null>(null)
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
    await fetchProfile()
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
  }

  async function updateProfile(data: Partial<UserProfile>) {
    const res = await authApi.updateProfile(data)
    profile.value = res
  }

  function logout() {
    token.value = null
    profile.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  return {
    profile,
    token,
    isLoggedIn,
    userRole,
    login,
    register,
    fetchProfile,
    updateProfile,
    logout,
  }
})
