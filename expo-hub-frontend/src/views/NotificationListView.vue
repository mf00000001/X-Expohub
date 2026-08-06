<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/index'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const items = ref<any[]>([])
const loading = ref(true)
const unread = ref(0)

onMounted(async () => {
  await fetchList()
  // mark all read
  http.post('/notifications/read-all').catch(()=>{})
})

async function fetchList() {
  try {
    const r: any = await http.get('/notifications?page_size=50')
    items.value = r?.data?.list || r?.list || []
    unread.value = r?.data?.unread || r?.unread || 0
  } catch {} finally { loading.value = false }
}

function handleClick(n: any) {
  if (n.link) router.push(n.link)
}
</script>

<template>
  <div class="page-container" style="max-width:600px;margin:0 auto">
    <h2 style="margin-bottom:16px">🔔 通知 <span v-if="unread" style="font-size:14px;color:#ef4444">({{ unread }}条未读)</span></h2>
    <div v-if="items.length===0 && !loading" style="text-align:center;padding:40px;color:var(--color-text-secondary)">暂无通知</div>
    <div v-for="n in items" :key="n.id" class="notif-card" :class="{unread:!n.is_read}" @click="handleClick(n)">
      <div class="n-title">{{ n.title }}</div>
      <div class="n-content" v-if="n.content">{{ n.content }}</div>
      <div class="n-time">{{ n.created_at?.slice(0,16)?.replace('T',' ') }}</div>
    </div>
  </div>
</template>

<style scoped>
.notif-card { padding:14px 16px; border-bottom:1px solid var(--color-border-lighter); cursor:pointer }
.notif-card.unread { background:#f0f4ff }
.notif-card:hover { background:var(--color-bg-page) }
.n-title { font-size:14px; font-weight:600 }
.n-content { font-size:12px; color:var(--color-text-secondary); margin-top:4px }
.n-time { font-size:11px; color:var(--color-text-placeholder); margin-top:4px }
</style>
