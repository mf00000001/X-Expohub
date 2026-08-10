import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserInfo } from '@/types/api'

export const useUserStore = defineStore('user', () => {
  const user = ref<UserInfo | null>(null)
  const token = ref<string | null>(null)
  const isLoggedIn = computed(() => !!token.value && !!user.value)

  function setAuth(authData: { access_token: string; user: UserInfo }) {
    token.value = authData.access_token
    user.value = authData.user
    localStorage.setItem('access_token', authData.access_token)
    localStorage.setItem('user_info', JSON.stringify(authData.user))
  }

  function restoreSession() {
    const savedToken = localStorage.getItem('access_token')
    const savedUser = localStorage.getItem('user_info')
    if (savedToken && savedUser) {
      try {
        token.value = savedToken
        user.value = JSON.parse(savedUser)
      } catch {
        logout()
      }
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
  }

  return {
    user,
    token,
    isLoggedIn,
    setAuth,
    restoreSession,
    logout,
  }
})
