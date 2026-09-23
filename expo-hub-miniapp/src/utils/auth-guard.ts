import { useUserStore } from '@/stores/user'

/**
 * 登录态守卫：未登录时弹提示并跳转登录页。
 * 用于身份绑定页面（个人资料 / 发布采购等）的 onLoad 首行。
 * @returns 是否已登录
 */
export function requireLogin(): boolean {
  const userStore = useUserStore()
  if (userStore.isLoggedIn) return true
  uni.showToast({ title: '请先登录', icon: 'none' })
  setTimeout(() => {
    uni.navigateTo({ url: '/pages/auth/login' })
  }, 400)
  return false
}
