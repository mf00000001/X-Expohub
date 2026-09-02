import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { useUserStore } from '@/stores/user'
import router from '@/router'

const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截器 — 直接从localStorage读token，避免Pinia初始化时序问题
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器
http.interceptors.response.use(
  (response: AxiosResponse) => {
    const body = response.data
    // Unwrap { success, data } envelope from backend
    return body.data !== undefined ? body.data : body
  },
  async (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || ''
      // 登出接口自身的 401 不递归处理(避免无限循环)
      if (!url.includes('/auth/logout')) {
        const userStore = useUserStore()
        // 仅本地清理:不调后端 logout,避免 token_version 全局递增把新登录 token 也失效
        userStore.localLogout()
        router.push('/login')
      }
    } else {
      // 演示监控：仅网络失败/5xx 视为控制台错误；4xx 为业务提示（页面已展示），避免噪音
      const status = error.response?.status
      if (!error.response || (status && status >= 500)) {
        const url = error.config?.url || ''
        console.error(`[api] ${error.config?.method?.toUpperCase() || 'GET'} ${url} -> ${status || 'ERR'} ${error.message || ''}`.trim())
      }
    }
    return Promise.reject(error)
  }
)

export default http
