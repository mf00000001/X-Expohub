<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import http from '@/api/index'

const router = useRouter()
const balance = ref(0)
const pos = ref({ x: 0, y: 0 })
const dragging = ref(false)
const offset = ref({ x: 0, y: 0 })
const show = ref(false)
// 拖动判定：记录按下起点与累计位移，超过阈值视为拖动，抑制随后的 click 跳转
let moved = false
let startPt = { x: 0, y: 0 }
const DRAG_THRESHOLD = 5 // px

const route = useRoute()
const hidden = computed(() => ['login','register'].includes(route.name as string))

let timer: ReturnType<typeof setInterval> | null = null

/* 悬浮球直径（与 .float-ball 的 width/height 一致） */
const BALL_SIZE = 56
/* 球与页脚顶边之间保留的安全间距 */
const FOOTER_GAP = 16
/* 初始位置右侧留白：保持原有视觉 x = innerWidth - 70 */
const INITIAL_RIGHT_OFFSET = 70
/* 兜底页脚高度：与 src/style.css 中 --footer-height 的默认值保持一致（仅变量读不到时使用） */
const FALLBACK_FOOTER_HEIGHT = 80

/**
 * 读取 :root 上的 --footer-height（纯 px 数值）
 * 页脚总高只在 style.css 里定义一次，这里读变量而不是再写一个数字，避免两处不一致
 */
function readFooterHeight(): number {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--footer-height')
  const n = parseFloat(raw)
  return Number.isFinite(n) ? n : FALLBACK_FOOTER_HEIGHT
}

/**
 * 页脚实际占位高 = --footer-height + iPhone 安全区 env(safe-area-inset-bottom)。
 * 安全区藏在 calc() 里，parseFloat 拆不出来，所以直接量一次 .app-footer 的实际高度：
 * 桌面端它就等于 --footer-height（80），iOS 全面屏会多出约 34px。
 * 这样球在两类设备上都停在「页脚 + 16px」上方，不会压住法律链接行；页脚未渲染时回退到变量值。
 */
function readFooterTotalHeight(): number {
  const base = readFooterHeight()
  const el = document.querySelector('.app-footer') as HTMLElement | null
  const measured = el ? el.getBoundingClientRect().height : 0
  return measured > base ? measured : base
}

/**
 * 把坐标夹取回可视区：
 *   x ∈ [0, innerWidth - 球宽]
 *   y ∈ [0, min(innerHeight - 球高, innerHeight - 页脚高 - 球高 - 16)]
 * resize / 横竖屏切换后即使之前拖到过边缘，也不会跑到屏幕外或压住页脚
 */
function clampIntoViewport(x: number, y: number, footerHeight: number) {
  const maxX = Math.max(0, window.innerWidth - BALL_SIZE)
  const maxY = Math.max(0, Math.min(
    window.innerHeight - BALL_SIZE,
    window.innerHeight - footerHeight - BALL_SIZE - FOOTER_GAP,
  ))
  return {
    x: Math.min(Math.max(x, 0), maxX),
    y: Math.min(Math.max(y, 0), maxY),
  }
}

/**
 * 计算并落地球的位置（初始与 resize 共用同一套算法）
 * @param reset true  = 重新算初始位置：右侧贴边 70px，底部让出「页脚 + 球高 + 16px」
 *              false = 保留用户拖到的位置，只做可视区夹取（窗口缩放 / 横竖屏）
 */
function placeBall(reset = false) {
  const footerHeight = readFooterTotalHeight()
  if (reset) {
    pos.value = clampIntoViewport(
      window.innerWidth - INITIAL_RIGHT_OFFSET,
      window.innerHeight - footerHeight - BALL_SIZE - FOOTER_GAP,
      footerHeight,
    )
    return
  }
  pos.value = clampIntoViewport(pos.value.x, pos.value.y, footerHeight)
}

/* resize 与 orientationchange 共用一个处理器：只夹取、不重置，避免缩放后把用户拖动的位置甩回默认点 */
function handleViewportChange() {
  placeBall()
}

onMounted(() => {
  // 初始位置统一走 placeBall()：先按「页脚总高 + 球高 + 16px」算，再夹取进可视区
  placeBall(true)
  // 部分机型横竖屏会先后触发 resize 与 orientationchange，重复调用是幂等的
  window.addEventListener('resize', handleViewportChange)
  window.addEventListener('orientationchange', handleViewportChange)
  if (hidden.value) return
  fetchBalance()
  timer = setInterval(fetchBalance, 60000)
})

onBeforeUnmount(() => {
  // 与 onMounted 里的注册一一对应，避免组件卸载后监听残留
  window.removeEventListener('resize', handleViewportChange)
  window.removeEventListener('orientationchange', handleViewportChange)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function fetchBalance() {
  if (!localStorage.getItem('access_token')) return
  try {
    const r: any = await http.get('/points/balance')
    balance.value = r?.data?.balance || r?.balance || 0
  } catch { balance.value = 0 }
}

function onDown(e: MouseEvent | TouchEvent) {
  dragging.value = true
  moved = false
  const p = 'touches' in e ? e.touches[0] : e
  startPt = { x: p.clientX, y: p.clientY }
  offset.value = { x: p.clientX - pos.value.x, y: p.clientY - pos.value.y }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  document.addEventListener('touchmove', onMove, { passive: false })
  document.addEventListener('touchend', onUp)
}

function onMove(e: MouseEvent | TouchEvent) {
  if (!dragging.value) return
  e.preventDefault()
  const p = 'touches' in e ? e.touches[0] : e
  const dx = p.clientX - startPt.x
  const dy = p.clientY - startPt.y
  if (Math.abs(dx) + Math.abs(dy) > DRAG_THRESHOLD) moved = true
  pos.value = { x: p.clientX - offset.value.x, y: p.clientY - offset.value.y }
}

function onUp() {
  dragging.value = false
  document.removeEventListener('mousemove', onMove)
  document.removeEventListener('mouseup', onUp)
  document.removeEventListener('touchmove', onMove)
  document.removeEventListener('touchend', onUp)
}

function onClick() {
  // 拖动结束后浏览器仍会派发 click：位移超过阈值则忽略，避免误跳转
  if (moved) { moved = false; return }
  router.push('/points')
}
</script>

<template>
  <div v-if="!hidden" class="float-ball" :style="{ left: pos.x + 'px', top: pos.y + 'px' }"
       @mousedown="onDown" @touchstart="onDown" @click="onClick">
    <span class="fb-icon">💰</span>
    <span class="fb-num">{{ balance }}</span>
  </div>
</template>

<style scoped>
.float-ball {
  position: fixed; z-index: 9999; width: 56px; height: 56px;
  border-radius: 50%; background: linear-gradient(135deg, #f59e0b, #ef4444);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  cursor: grab; user-select: none; box-shadow: 0 4px 16px rgba(239,68,68,0.3);
  transition: transform 0.15s;
}
.float-ball:active { cursor: grabbing; transform: scale(1.1) }
.fb-icon { font-size: 16px; line-height: 1 }
.fb-num { font-size: 13px; font-weight: 800; color: #fff; line-height: 1 }
</style>
