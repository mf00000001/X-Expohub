<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'
import http from '@/api/index'

const router = useRouter()
const userStore = useUserStore()

const stats = ref<any>(null)
const pendingCount = ref(0)
const exhStats = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [statsRes, pendingRes, exhRes] = await Promise.all([
      http.get('/admin/stats/overview'),
      http.get('/admin/users/pending-count'),
      http.get('/exhibitions', { params: { page_size: 10 } }),
    ])
    stats.value = statsRes?.data || statsRes
    pendingCount.value = pendingRes?.pending_count || pendingRes?.data?.pending_count || 0
    const exhs = exhRes?.list || exhRes?.data?.list || []
    // For each exhibition, get registration count
    for (const e of exhs.slice(0, 3)) {
      try {
        const regRes = await http.get(`/admin/exhibitions/${e.id}/registrations`)
        ;(e as any)._regCount = regRes?.data?.total || regRes?.total || 0
      } catch { (e as any)._regCount = 0 }
    }
    exhStats.value = exhs.slice(0, 3)
  } catch (err) {
    console.error('Failed to load dashboard:', err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <h1 class="page-title">管理后台 / Dashboard</h1>

      <LoadingSkeleton v-if="loading" :lines="6" />

      <div v-else>
        <!-- Stat cards -->
        <div class="stats-grid">
          <div class="stat-card">
            <span class="stat-value">{{ stats?.total_users || 0 }}</span>
            <span class="stat-desc">Users / 用户</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ stats?.total_exhibitions || 0 }}</span>
            <span class="stat-desc">Exhibitions / 展会</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ stats?.total_booths || 0 }}</span>
            <span class="stat-desc">Booths / 展位</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ stats?.total_products || 0 }}</span>
            <span class="stat-desc">Products / 展品</span>
          </div>
        </div>

        <!-- Pending badge -->
        <div class="card mt-6" style="padding:16px;display:flex;align-items:center;justify-content:space-between">
          <div>
            <span class="font-semibold">待审核展商 / Pending Exhibitors</span>
            <span v-if="pendingCount > 0" class="badge" style="margin-left:8px;background:var(--color-danger)">{{ pendingCount }}</span>
            <span v-else class="tag tag-success" style="margin-left:8px">0 - All clear</span>
          </div>
          <button class="btn btn-primary btn-sm" @click="router.push('/organizer/users')">管理用户 / Manage</button>
        </div>

        <!-- 展会统计 -->
        <div class="card mt-6" v-if="exhStats.length > 0" style="padding:16px">
          <h3 style="margin-bottom:12px">📊 各展会统计</h3>
          <div v-for="e in exhStats" :key="e.id" class="exh-stat-row">
            <span class="es-name">{{ e.title || e.name }}</span>
            <span class="es-stat">🏢 {{ e.total_booths || 0 }}展位</span>
            <span class="es-stat">📋 {{ (e as any)._regCount || 0 }}报名</span>
            <span class="es-stat">📅 {{ e.start_date?.slice(0,10) }}</span>
          </div>
        </div>

        <!-- Quick links -->
        <div class="grid grid-cols-2 gap-4 mt-6">
          <div class="card card-body cursor-pointer" @click="router.push('/organizer/exhibitions')">
            <h3 class="font-semibold">展会管理 / Exhibitions</h3>
            <p class="text-sm text-secondary">Manage your exhibitions</p>
          </div>
          <div class="card card-body cursor-pointer" @click="router.push('/organizer/statistics')">
            <h3 class="font-semibold">数据统计 / Statistics</h3>
            <p class="text-sm text-secondary">View detailed analytics</p>
          </div>
          <div class="card card-body cursor-pointer" @click="router.push('/organizer/exhibitions/create')">
            <h3 class="font-semibold">创建展会 / Create Exhibition</h3>
            <p class="text-sm text-secondary">Create a new exhibition</p>
          </div>
          <div class="card card-body cursor-pointer" @click="router.push('/organizer/exhibitions')">
            <h3 class="font-semibold">观展登记 / Registrations</h3>
            <p class="text-sm text-secondary">选择展会查看报名情况</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}
.stat-card {
  background: var(--color-white);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 24px 20px;
  text-align: center;
}
.stat-value {
  display: block;
  font-size: 32px;
  font-weight: 800;
  color: var(--color-primary);
}
.stat-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.font-semibold { font-weight: 600; }
</style>
