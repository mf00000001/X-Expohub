<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import http from '@/api/index'

const router = useRouter()

const stats = ref<any>(null)
const pendingCount = ref(0)
const exhStats = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [statsRes, pendingRes, exhRes]: any[] = await Promise.all([
      http.get('/admin/stats/overview'),
      http.get('/admin/users/pending-count'),
      http.get('/exhibitions', { params: { page_size: 10 } }),
    ])
    stats.value = statsRes?.data || statsRes
    pendingCount.value = pendingRes?.pending_count || pendingRes?.data?.pending_count || 0
    const exhs = exhRes?.list || exhRes?.data?.list || []
    // 2026-10-19 起平台自营：管理员查看全部展会，不再按归属过滤
    const topExhs = exhs.slice(0, 3)
    // 仅前 3 场展会额外补拉报名数量，避免一次性请求过多
    for (const e of topExhs) {
      try {
        const regRes: any = await http.get(`/admin/exhibitions/${e.id}/registrations`)
        ;(e as any)._regCount = regRes?.data?.total || regRes?.total || 0
      } catch {
        ;(e as any)._regCount = 0
      }
    }
    exhStats.value = topExhs
  } catch (err) {
    console.error('加载管理后台总览失败：', err)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div class="container page-wrapper">
      <!-- 页面标题 -->
      <h1 class="page-title">管理后台</h1>

      <LoadingSkeleton v-if="loading" :lines="6" />

      <div v-else>
        <!-- 核心指标卡片 -->
        <div class="stats-grid">
          <div class="stat-card">
            <span class="stat-value">{{ stats?.total_users || 0 }}</span>
            <span class="stat-desc">用户</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ stats?.total_exhibitions || 0 }}</span>
            <span class="stat-desc">展会</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ stats?.total_booths || 0 }}</span>
            <span class="stat-desc">展位</span>
          </div>
          <div class="stat-card">
            <span class="stat-value">{{ stats?.total_products || 0 }}</span>
            <span class="stat-desc">展品</span>
          </div>
        </div>

        <!-- 待审核提醒 -->
        <div class="card mt-6" style="padding:16px;display:flex;align-items:center;justify-content:space-between">
          <div>
            <span class="font-semibold">待审核展商</span>
            <span v-if="pendingCount > 0" class="badge" style="margin-left:8px;background:var(--color-danger)">{{ pendingCount }}</span>
            <span v-else class="tag tag-success" style="margin-left:8px">暂无待审核</span>
          </div>
          <button class="btn btn-primary btn-sm" @click="router.push('/admin/users')">管理用户</button>
        </div>

        <!-- 各展会统计：点击行直接进入该展会的报名名单 -->
        <div class="card mt-6" v-if="exhStats.length > 0" style="padding:16px">
          <h3 style="margin-bottom:12px">📊 各展会统计</h3>
          <div v-for="e in exhStats" :key="e.id" class="exh-stat-row" style="cursor:pointer" @click="router.push('/admin/exhibitions/' + e.id + '/registrations')" title="查看并导出报名名单">
            <span class="es-name">{{ e.title || e.name }}</span>
            <span class="es-stat">🏢 {{ e.total_booths || 0 }} 个展位</span>
            <span class="es-stat">📋 {{ (e as any)._regCount || 0 }} 人报名 ›</span>
            <span class="es-stat">📅 {{ e.start_date?.slice(0,10) }}</span>
          </div>
        </div>

        <!-- 快捷入口 -->
        <div class="grid grid-cols-2 gap-4 mt-6">
          <div class="card card-body cursor-pointer" @click="router.push('/admin/exhibitions')">
            <h3 class="font-semibold">展会管理</h3>
            <p class="text-sm text-secondary">管理全部展会；进入列表后点“登记”可查看报名名单</p>
          </div>
          <div class="card card-body cursor-pointer" @click="router.push('/admin/boss')">
            <h3 class="font-semibold">平台总览（Boss 看板）</h3>
            <p class="text-sm text-secondary">平台级经营与统计数据</p>
          </div>
          <div class="card card-body cursor-pointer" @click="router.push('/admin/exhibitions/create')">
            <h3 class="font-semibold">创建展会</h3>
            <p class="text-sm text-secondary">新建一场展会</p>
          </div>
          <!-- 展馆选择入口：汇总对比全国展馆，辅助确定办展场地 -->
          <div class="card card-body cursor-pointer" style="border-color:#93c5fd;background:#eff6ff" @click="router.push('/admin/venue-select')">
            <h3 class="font-semibold">🏛️ 展馆选择</h3>
            <p class="text-sm text-secondary">汇总对比全国展馆，挑选办展场地</p>
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
