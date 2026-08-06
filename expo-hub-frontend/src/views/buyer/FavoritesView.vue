<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/index'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const loading = ref(true)
const favProducts = ref<any[]>([])
const favBooths = ref<any[]>([])
const appointments = ref<any[]>([])

onMounted(async () => {
  try {
    const [favRes, apptRes] = await Promise.all([
      http.get('/favorites/my'),
      http.get('/appointments/my'),
    ])
    favProducts.value = (favRes as any)?.data?.products || (favRes as any)?.products || []
    favBooths.value = (favRes as any)?.data?.micro_booths || (favRes as any)?.micro_booths || []
    appointments.value = (apptRes as any)?.data?.list || (apptRes as any)?.list || []
  } catch {} finally { loading.value = false }
})

// Group by exhibition
const groupedAppts = computed(() => {
  const m: Record<string, any[]> = {}
  for (const a of appointments.value) {
    const t = a.exhibition_title || '未指定展会'
    if (!m[t]) m[t] = []
    m[t].push(a)
  }
  return m
})
</script>

<template>
  <div class="page-container" style="max-width:700px;margin:0 auto">
    <h2>📋 我的观展清单</h2>

    <div v-if="loading" style="text-align:center;padding:40px">加载中...</div>

    <!-- 预约 -->
    <div v-if="Object.keys(groupedAppts).length > 0" class="section">
      <h3>📅 已预约见面</h3>
      <div v-for="(items, exhTitle) in groupedAppts" :key="exhTitle" class="card" style="margin-bottom:12px;padding:16px">
        <h4 style="margin-bottom:8px">🎪 {{ exhTitle }}</h4>
        <div v-for="a in items" :key="a.id" class="appt-row">
          <span>{{ a.counterpart_name }}</span>
          <span class="tag tag-success">{{ a.time_slot }}</span>
        </div>
      </div>
    </div>

    <!-- 收藏的微展位 -->
    <div class="section">
      <h3>⭐ 收藏的供应商</h3>
      <EmptyState v-if="favBooths.length===0" message="还没有收藏供应商，去微展位广场逛逛" icon="🏪" />
      <div v-else class="fav-grid">
        <div v-for="b in favBooths" :key="b.id" class="fav-card" @click="router.push('/micro-booths/'+b.id)">
          <span>🏪 {{ b.name }}</span><span class="text-muted">{{ b.industry_domain }}</span>
        </div>
      </div>
    </div>

    <!-- 收藏的展品 -->
    <div class="section">
      <h3>📦 收藏的展品</h3>
      <EmptyState v-if="favProducts.length===0" message="还没有收藏展品" icon="📦" />
      <div v-else class="fav-grid">
        <div v-for="p in favProducts" :key="p.id" class="fav-card" @click="router.push('/products/'+p.id)">
          <span>📦 {{ p.name }}</span><span class="text-muted">{{ p.category }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section { margin-bottom:24px } .section h3 { margin-bottom:12px; font-size:16px }
.fav-grid { display:flex; flex-direction:column; gap:8px }
.fav-card { padding:12px 16px; background:var(--color-bg-card); border-radius:8px; cursor:pointer; display:flex; justify-content:space-between; box-shadow:0 1px 3px rgba(0,0,0,0.04) }
.fav-card:hover { background:var(--color-bg-page) }
.appt-row { display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--color-border-lighter); font-size:14px }
</style>
