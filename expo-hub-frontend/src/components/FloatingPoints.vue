<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
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

onMounted(() => {
  pos.value = { x: window.innerWidth - 70, y: window.innerHeight - 120 }
  if (hidden.value) return
  fetchBalance()
  timer = setInterval(fetchBalance, 60000)
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
