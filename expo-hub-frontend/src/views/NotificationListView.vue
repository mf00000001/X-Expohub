<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/index'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const items = ref<any[]>([])
const loading = ref(true)
const unread = ref(0)

onMounted(fetchList)

async function fetchList() {
  try {
    const r: any = await http.get('/notifications?page_size=50')
    items.value = r?.data?.list || r?.list || []
    unread.value = r?.data?.unread || r?.unread || 0
  } catch {} finally { loading.value = false }
}

async function handleClick(n: any) {
  // 未读先标已读（后端 POST /notifications/{id}/read）
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
  <div class="page-container" style="max-width:600px;margin:0 auto">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2 style="margin:0">🔔 通知 <span v-if="unread" style="font-size:14px;color:#ef4444">({{ unread }}条未读)</span></h2>
      <button v-if="unread" class="btn btn-outline btn-sm" @click="markAllRead">全部标为已读</button>
    </div>
    <div v-if="items.length===0 && !loading" style="text-align:center;padding:40px;color:var(--color-text-secondary)">暂无通知</div>
    <div v-for="n in items" :key="n.id" class="notif-card" :class="{unread:!n.is_read}" @click="handleClick(n)">
      <div class="n-title"><span v-if="!n.is_read" class="dot"></span>{{ n.title }}</div>
      <div class="n-content" v-if="n.content">{{ n.content }}</div>
      <div class="n-time">{{ n.created_at?.slice(0,16)?.replace('T',' ') }}</div>
    </div>
  </div>
</template>

<style scoped>
.notif-card { padding:14px 16px; border-bottom:1px solid var(--color-border-lighter); cursor:pointer }
.notif-card.unread { background:#f0f4ff }
.notif-card:hover { background:var(--color-bg-page) }
.n-title { font-size:14px; font-weight:600; display:flex; align-items:center; gap:6px }
.dot { width:7px;height:7px;border-radius:50%;background:#ef4444;display:inline-block;flex-shrink:0 }
.n-content { font-size:12px; color:var(--color-text-secondary); margin-top:4px }
.n-time { font-size:11px; color:var(--color-text-placeholder); margin-top:4px }
</style>
