/**
 * 通用 API 类型定义
 */

/** 标准 API 响应 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/** 分页响应 */
export interface PaginatedResponse<T = unknown> {
  code: number
  message: string
  data: {
    list: T[]
    total: number
    page: number
    pageSize: number
    totalPages: number
  }
}

/** 分页请求参数 */
export interface PaginationParams {
  page?: number
  pageSize?: number
}

/** 登录请求 */
export interface LoginRequest {
  username: string
  password: string
}

/** 登录响应 */
export interface LoginResponse {
  accessToken: string
  refreshToken: string
  userId: string
  username: string
  role: string
}

/** 注册请求 */
export interface RegisterRequest {
  username: string
  password: string
  role: string
  email?: string
  phone?: string
  companyName?: string
}

/** 用户信息 */
export interface UserProfile {
  userId: string
  username: string
  role: string
  email: string
  phone: string
  companyName: string
  avatar: string
  createdAt: string
}
