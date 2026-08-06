/**
 * 角色权限工具（新角色体系：visitor / exhibitor / organizer / boss）
 */

/** 路由 → 允许访问的角色列表 */
export const ROUTE_ROLE_MAP: Record<string, string[]> = {
  // 公共路由（所有角色均可访问）
  '/': ['visitor', 'exhibitor', 'organizer', 'boss'],
  '/login': [],
  '/register': [],
  '/exhibitions': ['visitor', 'exhibitor', 'organizer', 'boss'],
  '/booths': ['visitor', 'exhibitor', 'organizer', 'boss'],
  '/products': ['visitor', 'exhibitor', 'organizer', 'boss'],
  '/procurements': ['visitor', 'exhibitor', 'organizer', 'boss'],
  '/messages': ['visitor', 'exhibitor', 'organizer', 'boss'],
  '/profile': ['visitor', 'exhibitor', 'organizer', 'boss'],
  '/settings': ['visitor', 'exhibitor', 'organizer', 'boss'],
  '/search': ['visitor', 'exhibitor', 'organizer', 'boss'],

  // 观众专属
  '/visitor': ['visitor'],
  '/visitor/registrations': ['visitor'],
  '/visitor/procurements': ['visitor'],
  '/visitor/procurements/create': ['visitor'],

  // 参展商专属
  '/exhibitor': ['exhibitor'],
  '/exhibitor/dashboard': ['exhibitor'],
  '/exhibitor/booths': ['exhibitor'],
  '/exhibitor/products': ['exhibitor'],
  '/exhibitor/products/create': ['exhibitor'],
  '/exhibitor/products/:id/edit': ['exhibitor'],
  '/exhibitor/matches': ['exhibitor'],

  // 主办方专属
  '/organizer': ['organizer'],
  '/organizer/dashboard': ['organizer'],
  '/organizer/exhibitions': ['organizer'],
  '/organizer/exhibitions/create': ['organizer'],
  '/organizer/exhibitions/:id/edit': ['organizer'],
  '/organizer/exhibitions/:id/booths': ['organizer'],
  '/organizer/exhibitions/:id/booths/create': ['organizer'],
  '/organizer/exhibitions/:id/booths/assign': ['organizer'],
  '/organizer/exhibitions/:id/registrations': ['organizer'],
  '/organizer/statistics': ['organizer'],

  // 超级管理员专属
  '/boss': ['boss'],
  '/boss/dashboard': ['boss'],
  '/boss/stats': ['boss'],
  '/boss/stats/users': ['boss'],
  '/boss/stats/exhibitions': ['boss'],
  '/boss/approvals': ['boss'],
  '/boss/approvals/:id': ['boss'],
  '/boss/teams': ['boss'],
  '/boss/teams/create': ['boss'],
  '/boss/teams/:id/members': ['boss'],
}

/**
 * 检查指定角色是否有权访问某路由
 */
export function checkRoleAccess(routePath: string, userRole: string): boolean {
  const allowedRoles = ROUTE_ROLE_MAP[routePath]
  // 如果路由未在映射表中定义，默认允许访问
  if (!allowedRoles) return true
  // 空数组表示仅未登录可访问（如 /login）
  if (allowedRoles.length === 0) return false
  return allowedRoles.includes(userRole)
}
