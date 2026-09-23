/**
 * uni.request 封装
 * - 自动注入 Authorization Bearer token
 * - 自动解包后端 { success, code, message, data } → data
 * - 401 时单飞刷新 token(防并发重复刷新)并自动重试原请求
 * - 刷新失败或没有 refresh_token → 清 token 并跳登录页
 */
import { BASE_URL } from '@/config'

export interface RequestOptions {
  url: string
  method?: UniApp.RequestOptions['method']
  /** 请求体 */
  data?: Record<string, unknown>
  /** 查询参数(会拼到 url 上，忽略空值) */
  params?: Record<string, unknown>
  /** 跳过 401 刷新逻辑 */
  skipAuth?: boolean
  /** 内部：标记是否已重试过 */
  _retried?: boolean
}

/** 后端分页列表的统一返回结构（实际字段为 list/total/page/pageSize/totalPages） */
export interface PageResult<T> {
  list?: T[]
  items?: T[]
  results?: T[]
  total?: number
  page?: number
  page_size?: number
  pageSize?: number
  totalPages?: number
  [key: string]: unknown
}

// 刷新锁与等待队列
let isRefreshing = false
let failedQueue: Array<{
  resolve: () => void
  reject: (err: unknown) => void
}> = []

function processQueue(error: unknown) {
  failedQueue.forEach((p) => {
    if (error) p.reject(error)
    else p.resolve()
  })
  failedQueue = []
}

/** 把 params 拼到 url 上（过滤空值） */
function buildUrl(url: string, params?: Record<string, unknown>): string {
  const base = url.startsWith('http') ? url : `${BASE_URL}${url}`
  if (!params) return base
  const qs = Object.keys(params)
    .filter((k) => params[k] !== undefined && params[k] !== null && params[k] !== '')
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(String(params[k]))}`)
    .join('&')
  return qs ? `${base}${base.includes('?') ? '&' : '?'}${qs}` : base
}

/** 把非 2xx 响应归一化成带 statusCode / detail 的错误对象 */
function normalizeError(res: UniApp.RequestSuccessCallbackResult): Error {
  const body = res.data as { detail?: unknown; message?: string; msg?: string } | undefined
  const message =
    (typeof body?.detail === 'string' && body.detail) ||
    body?.message ||
    body?.msg ||
    `请求失败(${res.statusCode})`
  const err = new Error(message) as Error & { statusCode?: number; detail?: unknown }
  err.statusCode = res.statusCode
  err.detail = body?.detail
  return err
}

function redirectToLogin() {
  const pages = getCurrentPages()
  const current = pages[pages.length - 1]?.route || ''
  if (!current.includes('auth/login')) {
    uni.reLaunch({ url: '/pages/auth/login' })
  }
}

/** 用 refresh_token 换新双令牌（裸 uni.request，不经过本封装避免递归） */
function doRefresh(): Promise<string> {
  const refreshToken = uni.getStorageSync('refresh_token') as string
  if (!refreshToken) {
    uni.removeStorageSync('access_token')
    return Promise.reject(new Error('NO_REFRESH_TOKEN'))
  }
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}/auth/refresh`,
      method: 'POST',
      data: { refresh_token: refreshToken },
      header: { 'Content-Type': 'application/json' },
      timeout: 15000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          const body = res.data as { data?: Record<string, unknown> } & Record<string, unknown>
          const inner = body.data && 'access_token' in body.data ? body.data : body
          uni.setStorageSync('access_token', inner.access_token)
          if (inner.refresh_token) {
            uni.setStorageSync('refresh_token', inner.refresh_token)
          }
          resolve(String(inner.access_token))
        } else {
          uni.removeStorageSync('access_token')
          uni.removeStorageSync('refresh_token')
          reject(new Error('刷新令牌失败'))
        }
      },
      fail: (err) => reject(new Error(err.errMsg || '刷新令牌失败')),
    })
  })
}

export function request<T = unknown>(options: RequestOptions): Promise<T> {
  const { url, method = 'GET', data, params, skipAuth, _retried } = options

  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync('access_token') as string
    const header: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) header.Authorization = `Bearer ${token}`

    uni.request({
      url: buildUrl(url, params),
      method,
      data,
      header,
      timeout: 15000,
      success: (res) => {
        // 401 → 刷新令牌并重试一次
        if (res.statusCode === 401 && !skipAuth && !_retried) {
          if (isRefreshing) {
            // 已有刷新在进行中，排队等待后重试
            failedQueue.push({
              resolve: () => request<T>({ ...options, _retried: true }).then(resolve, reject),
              reject,
            })
            return
          }
          isRefreshing = true
          doRefresh()
            .then(() => {
              processQueue(null)
              return request<T>({ ...options, _retried: true })
            })
            .then(resolve, reject)
            .finally(() => {
              isRefreshing = false
            })
          return
        }

        if (res.statusCode >= 200 && res.statusCode < 300) {
          const body = res.data as { success?: boolean; data?: T } | null
          if (body && typeof body === 'object' && 'success' in body && 'data' in body) {
            resolve(body.data as T)
          } else {
            resolve(body as T)
          }
        } else {
          // 401：skipAuth 请求(登录/注册)直接透出后端错误，不跳登录不清 token；
          // 其余 401(刷新后仍失败)判为登录失效，清 token 跳登录
          if (res.statusCode === 401 && !skipAuth) {
            uni.removeStorageSync('access_token')
            uni.removeStorageSync('refresh_token')
            redirectToLogin()
          }
          reject(normalizeError(res))
        }
      },
      fail: (err) => {
        reject(new Error(err.errMsg || '网络请求失败'))
      },
    })
  })
}

// 便捷方法
export const http = {
  get: <T = unknown>(url: string, options?: Omit<RequestOptions, 'url' | 'method'>) =>
    request<T>({ url, method: 'GET', ...options }),
  post: <T = unknown>(url: string, data?: Record<string, unknown>, options?: Omit<RequestOptions, 'url' | 'method' | 'data'>) =>
    request<T>({ url, method: 'POST', data, ...options }),
  put: <T = unknown>(url: string, data?: Record<string, unknown>, options?: Omit<RequestOptions, 'url' | 'method' | 'data'>) =>
    request<T>({ url, method: 'PUT', data, ...options }),
  delete: <T = unknown>(url: string, options?: Omit<RequestOptions, 'url' | 'method'>) =>
    request<T>({ url, method: 'DELETE', ...options }),
}

export default request
