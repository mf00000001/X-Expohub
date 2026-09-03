<template>
  <view class="page">
    <view class="top">
      <text class="h">🔔 通知</text>
      <button v-if="unread > 0" class="mini" size="mini" @click="markAll">全部已读</button>
    </view>
    <view class="filters">
      <text :class="['chip', filter === 'all' ? 'on' : '']" @click="filter = 'all'">全部</text>
      <text :class="['chip', filter === 'deal' ? 'on' : '']" @click="filter = 'deal'">撮合</text>
      <text :class="['chip', filter === 'other' ? 'on' : '']" @click="filter = 'other'">其他</text>
    </view>

    <view class="card" v-for="n in shown" :key="n.id" @click="open(n)">
      <view class="row">
        <text class="ic">{{ iconOf(n) }}</text>
        <view class="main">
          <view class="trow"><text v-if="!n.is_read" class="dot" />{{ n.title }}</view>
          <text class="content" v-if="n.content">{{ n.content }}</text>
          <text class="time">{{ fmt(n.created_at) }}</text>
        </view>
      </view>
    </view>
    <view v-if="shown.length === 0 && loaded" class="empty">暂无通知</view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { request } from '@/utils/request'

const items = ref<any[]>([])
const loaded = ref(false)
const unread = ref(0)
const filter = ref<'all' | 'deal' | 'other'>('all')

const META: Record<string, { g: string; i: string }> = {
  bid: { g: 'deal', i: '📩' }, match: { g: 'deal', i: '🎉' },
  favorite: { g: 'other', i: '❤️' }, message: { g: 'other', i: '💬' },
}
const iconOf = (n: any) => (META[n.type] || { i: '🔔' }).i
const shown = computed(() => {
  const list = [...items.value].sort((a, b) => Number(!!b.is_read) - Number(!!a.is_read))
  if (filter.value === 'all') return list
  const g = filter.value
  return list.filter((n) => (META[n.type] || { g: 'other' }).g === g)
})

onShow(load)

async function load() {
  try {
    const r: any = await request({ url: '/notifications?page_size=50' })
    items.value = r?.list || r?.items || []
    unread.value = r?.unread || 0
  } catch { items.value = [] } finally { loaded.value = true }
}

async function open(n: any) {
  if (!n.is_read) {
    n.is_read = true
    unread.value = Math.max(0, unread.value - 1)
    request({ url: `/notifications/${n.id}/read`, method: 'POST' }).catch(() => {})
  }
  if (n.link) uni.navigateTo({ url: webPath2mp(n.link) })
}

// 网页路径 → 小程序页（仅支持已内置的目标）
function webPath2mp(link: string): string {
  const id = (link.match(/procurements\/(\d+)/) || [])[1]
  if (link.includes('/procurements/') && id) return '/pages/tickets/my' // 占位：小程序暂无采购详情页
  if (link.includes('/exhibitor/matches')) return '/pages/tickets/my'
  if (link.includes('/messages')) return '/pages/tickets/my'
  return '/pages/index/index'
}

async function markAll() {
  await request({ url: '/notifications/read-all', method: 'POST' }).catch(() => {})
  items.value.forEach((n) => { n.is_read = true })
  unread.value = 0
}

function fmt(s?: string) {
  return s ? String(s).slice(0, 16).replace('T', ' ') : ''
}
</script>

<style scoped>
.page { padding: 16px; background: #f5f6f8; min-height: 100vh; }
.top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.h { font-size: 18px; font-weight: 700; }
.mini { background: #fff; border: 1px solid #d0d3da; color: #555; font-size: 12px; }
.filters { display: flex; gap: 8px; margin-bottom: 10px; }
.chip { font-size: 13px; padding: 4px 12px; border-radius: 14px; background: #fff; color: #666; }
.chip.on { background: #4f6ef7; color: #fff; }
.card { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 8px; }
.row { display: flex; gap: 10px; }
.ic { font-size: 18px; }
.main { flex: 1; }
.trow { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #ef4444; }
.content { display: block; font-size: 12px; color: #666; margin-top: 4px; word-break: break-all; }
.time { display: block; font-size: 11px; color: #999; margin-top: 4px; }
.empty { text-align: center; color: #999; padding: 40px 0; }
</style>
