<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/index'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const items = ref<any[]>([])
const loading = ref(true)
const unread = ref(0)
const filter = ref<'all' | 'deal' | 'other'>('all')

// 类型 → 分组/图标
const TYPE_META: Record<string, { group: 'deal' | 'other'; icon: string }> = {
  bid: { group: 'deal', icon: '📩' },
  match: { group: 'deal', icon: '🎉' },
  favorite: { group: 'other', icon: '❤️' },
  message: { group: 'other', icon: '💬' },
  system: { group: 'other', icon: '⚙️' },
}
function meta(n: any) {
  return TYPE_META[n.type] || { group: 'other' as const, icon: '🔔' }
}

const shown = computed(() => {
  const list = [...items.value]
  // 未读置顶
  list.sort((a, b) => Number(Boolean(b.is_read)) - Number(Boolean(a.is_read)))
  if (filter.value === 'all') return list
  return list.filter((n) => meta(n).group === filter.value)
})
const unreadDeal = computed(() => items.value.filter((n) => !n.is_read && meta(n).group === 'deal').length)

onMounted(fetchList)

async function fetchList() {
  try {
    const r: any = await http.get('/notifications?page_size=50')
    items.value = r?.data?.list || r?.list || []
    unread.value = r?.data?.unread || r?.unread || 0
  } catch {} finally { loading.value = false }
}

async function handleClick(n: any) {
  if (!n.is_read) {
    n.is_read = true
    unread.value = Math.max(0, unread.value - 1)
    http.post(`/notifications/${n.id}/read`).catch(() => {})
  }
  if (n.link) router.push(n.link)
}

async function markAllRead() {
  await http.post('/notifications/read-all').catch(() => {})
  items.value.forEach((n) => { n.is_read = true })
  unread.value = 0
}
</script>

<template>
  <div class="page-container" style="max-width:620px;margin:0 auto">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h2 style="margin:0">🔔 通知
        <span v-if="unread" style="font-size:14px;color:#ef4444">({{ unread }}未读)</span>
        <span v-if="unreadDeal" style="font-size:12px;color:#4f6ef7;margin-left:6px">其中撮合 {{ unreadDeal }}</span>
      </h2>
      <button v-if="unread" class="btn btn-outline btn-sm" @click="markAllRead">全部标为已读</button>
    </div>

    <div class="filters" style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn btn-sm" :class="filter==='all' ? 'btn-primary' : 'btn-outline'" @click="filter='all'">全部</button>
      <button class="btn btn-sm" :class="filter==='deal' ? 'btn-primary' : 'btn-outline'" @click="filter='deal'">撮合动态</button>
      <button class="btn btn-sm" :class="filter==='other' ? 'btn-primary' : 'btn-outline'" @click="filter='other'">其他</button>
    </div>

    <div v-if="items.length===0 && !loading" style="text-align:center;padding:40px;color:var(--color-text-secondary)">暂无通知</div>
    <div v-for="n in shown" :key="n.id" class="notif-card" :class="{unread:!n.is_read}" @click="handleClick(n)">
      <div class="n-icon">{{ meta(n).icon }}</div>
      <div class="n-main">
        <div class="n-title"><span v-if="!n.is_read" class="dot"></span>{{ n.title }}</div>
        <div class="n-content" v-if="n.content">{{ n.content }}</div>
        <div class="n-time">{{ n.created_at?.slice(0,16)?.replace('T',' ') }}<span v-if="n.type" class="n-type">· {{ n.type }}</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notif-card { padding:12px 14px; border-bottom:1px solid var(--color-border-lighter); cursor:pointer; display:flex; gap:12px; align-items:flex-start }
.notif-card.unread { background:#f0f4ff }
.notif-card:hover { background:var(--color-bg-page) }
.n-icon { font-size:18px; line-height:1.4 }
.n-main { flex:1; min-width:0 }
.n-title { font-size:14px; font-weight:600; display:flex; align-items:center; gap:6px }
.dot { width:7px;height:7px;border-radius:50%;background:#ef4444;display:inline-block;flex-shrink:0 }
.n-content { font-size:12px; color:var(--color-text-secondary); margin-top:4px; word-break:break-all }
.n-time { font-size:11px; color:var(--color-text-placeholder); margin-top:4px }
.n-type { color:var(--color-text-placeholder) }
</style>
