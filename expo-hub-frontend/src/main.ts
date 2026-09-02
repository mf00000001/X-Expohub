import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

// ============ 演示监控：控制台错误回传钩子（纯观测，不影响功能） ============
// 所有 console.error / 未捕获异常 / 网络失败都会上报到后端 /api/debug/console，
// 供演示期问题统计。去抖 + 去重，避免刷屏。
;(function installConsoleReporter() {
  const HEADERS = { 'Content-Type': 'application/json', 'X-Debug-Log': 'expohub-demo-monitor' }
  let lastSent = ''
  let lastTs = 0
  function report(level: string, msg: string) {
    const now = Date.now()
    if (msg === lastSent && now - lastTs < 2000) return // 连续重复抑制
    lastSent = msg
    lastTs = now
    fetch('/api/debug/console', {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify({ level, msg: String(msg).slice(0, 2000), url: location.href })
    }).catch(() => { /* 静默 */ })
  }
  const origError = console.error
  console.error = (...args: unknown[]) => {
    origError.apply(console, args)
    report('error', args.map(String).join(' '))
  }
  const origWarn = console.warn
  console.warn = (...args: unknown[]) => {
    origWarn.apply(console, args)
    report('warn', args.map(String).join(' '))
  }
  window.addEventListener('unhandledrejection', (e) => {
    report('unhandledrejection', String((e.reason && (e.reason.stack || e.reason)) || e.reason))
  })
  window.addEventListener('error', (e) => {
    report('windowerror', `${e.message} @ ${e.filename || ''}:${e.lineno || ''}`)
  })
})()

const app = createApp(App)

// 安装 Pinia 状态管理
const pinia = createPinia()
app.use(pinia)

// 安装 Vue Router
app.use(router)

app.mount('#app')
