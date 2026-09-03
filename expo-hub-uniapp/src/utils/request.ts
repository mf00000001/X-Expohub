// ExpoHub 小程序请求封装（对齐 web 端 axios 语义：自动解包 {success,data}）
// 后端地址：开发默认本机 8002；真机调试改为电脑局域网 IP，并在微信开发者工具关闭域名校验
const BASE_URL = 'http://127.0.0.1:8002/api'

export function getToken(): string {
  return (uni.getStorageSync('access_token') as string) || ''
}

export function logoutLocal() {
  uni.removeStorageSync('access_token')
  uni.removeStorageSync('expo_user')
}

interface Options {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: any
  auth?: boolean
}

export function request<T = any>(opt: Options): Promise<T> {
  return new Promise((resolve, reject) => {
    const header: Record<string, string> = { 'Content-Type': 'application/json' }
    if (opt.auth !== false) {
      const tk = getToken()
      if (tk) header.Authorization = 'Bearer ' + tk
    }
    uni.request({
      url: BASE_URL + opt.url,
      method: opt.method || 'GET',
      data: opt.data || {},
      header,
      timeout: 15000,
      success: (res) => {
        const body: any = res.data
        if (res.statusCode === 401) {
          logoutLocal()
          uni.showToast({ title: '登录已过期，请重新登录', icon: 'none' })
          setTimeout(() => {
            uni.reLaunch({ url: '/pages/login/login' })
          }, 800)
          reject(new Error('401'))
          return
        }
        if (res.statusCode >= 400) {
          const msg = body?.detail || body?.message || body?.msg || '请求失败(' + res.statusCode + ')'
          reject(new Error(msg))
          return
        }
        // 解包 { success, code, data } 信封（与 web 端 axios 拦截器一致）
        resolve(body && typeof body === 'object' && 'data' in body && body.data !== undefined ? body.data : body)
      },
      fail: (err) => reject(new Error(err.errMsg || '网络错误')),
    })
  })
}

export function normList(raw: any): any {
  if (Array.isArray(raw)) return { list: raw, total: raw.length }
  const r = raw || {}
  const arr = r.list ?? r.items ?? r.results ?? r.data ?? r.matches ?? []
  return {
    list: arr,
    items: arr,
    matches: arr,
    total: r.total ?? r.count ?? (Array.isArray(arr) ? arr.length : 0),
    page: r.page ?? 1,
    pageSize: r.pageSize ?? r.page_size ?? arr.length,
    totalPages: r.totalPages ?? r.total_pages ?? 1,
  }
}
