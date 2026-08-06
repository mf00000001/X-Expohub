import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  /** 未读消息数 */
  const unreadCount = ref(0)

  /** 全局加载状态 */
  const loading = ref(false)

  function setUnreadCount(count: number): void {
    unreadCount.value = count
  }

  function incrementUnread(): void {
    unreadCount.value++
  }

  function setLoading(val: boolean): void {
    loading.value = val
  }

  return {
    unreadCount,
    loading,
    setUnreadCount,
    incrementUnread,
    setLoading,
  }
})
