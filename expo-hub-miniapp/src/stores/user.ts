import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type UserProfile } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const profile = ref<UserProfile | null>(null)
  const token = ref<string>((uni.getStorageSync('access_token') as string) || '')

  const isLoggedIn = computed(() => !!token.value)
  const userRole = computed(() => profile.value?.role || '')

  function saveTokens(res: { access_token: string; refresh_token?: string }) {
    token.value = res.access_token
    uni.setStorageSync('access_token', res.access_token)
    if (res.refresh_token) {
      uni.setStorageSync('refresh_token', res.refresh_token)
    }
  }

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    saveTokens(res)
    await fetchProfile()
  }

  async function register(data: {
    username: string
    email: string
    password: string
    role?: string
    company_name?: string
    business_license?: string
  }) {
    const res = await authApi.register(data)
    saveTokens(res)
    await fetchProfile()
  }

  async function wechatLogin(code: string, nickname?: string, avatarUrl?: string) {
    const res = await authApi.wechatLogin({ code, nickname, avatar_url: avatarUrl })
    saveTokens(res)
    await fetchProfile()
  }

  async function fetchProfile() {
    const res = await authApi.getProfile()
    profile.value = res
  }

  async function updateProfile(data: Record<string, unknown>) {
    const res = await authApi.updateProfile(data)
    profile.value = res
  }

  function logout() {
    token.value = ''
    profile.value = null
    uni.removeStorageSync('access_token')
    uni.removeStorageSync('refresh_token')
  }

  return {
    profile,
    token,
    isLoggedIn,
    userRole,
    login,
    register,
    wechatLogin,
    fetchProfile,
    updateProfile,
    logout,
  }
})
