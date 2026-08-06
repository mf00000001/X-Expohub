/**
 * 认证相关工具函数
 * Token 和用户信息存储在 localStorage
 */

const TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'
const USER_INFO_KEY = 'expo_user_profile'

// ---- Token 操作 ----

export function saveTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export function getTokens(): { accessToken: string | null; refreshToken: string | null } {
  return {
    accessToken: localStorage.getItem(TOKEN_KEY),
    refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY),
  }
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

// ---- 用户信息操作 ----

export interface SavedUserInfo {
  userId: string
  username: string
  role: string
}

export function saveUserInfo(info: SavedUserInfo): void {
  localStorage.setItem(USER_INFO_KEY, JSON.stringify(info))
}

export function getUserInfo(): SavedUserInfo | null {
  const raw = localStorage.getItem(USER_INFO_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as SavedUserInfo
  } catch {
    return null
  }
}

export function clearUserInfo(): void {
  localStorage.removeItem(USER_INFO_KEY)
}

// ---- 便捷判断 ----

export function isLoggedIn(): boolean {
  return !!localStorage.getItem(TOKEN_KEY)
}

// ---- 角色首页路由 ----

/**
 * 根据角色返回对应的首页路径（新角色体系：visitor / exhibitor / organizer / boss）
 */
export function getRoleHomePath(role: string): string {
  const roleHomeMap: Record<string, string> = {
    visitor: '/',
    buyer: '/buyer/dashboard',
    exhibitor: '/exhibitor/dashboard',
    organizer: '/organizer/dashboard',
    admin: '/organizer/dashboard',
  }
  return roleHomeMap[role] || '/'
}
