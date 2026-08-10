<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import StatsCard from '@/components/StatsCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import { getExhibitionStats } from '@/api/dashboard'

const router = useRouter()
const stats = ref<any>(null)
const loading = ref(true)
const error = ref('')

async function fetchStats() {
  loading.value = true
  error.value = ''
  try {
    const data = await getExhibitionStats()
    stats.value = data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载统计数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchStats)
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">数据统计</h1>
        <button class="btn btn-outline btn-sm" @click="router.push('/organizer/dashboard')">
          ← 返回后台
        </button>
      </div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchStats">重试</button>
      </div>

      <div v-else>
        <div class="grid grid-cols-1 grid-cols-2 grid-cols-4 gap-4 mb-6">
          <StatsCard title="展会总数" :value="stats?.total_exhibitions ?? 0" icon="🎪" />
          <StatsCard title="活跃展会" :value="stats?.active_exhibitions ?? 0" icon="🟢" />
          <StatsCard title="总报名数" :value="stats?.total_registrations ?? 0" icon="👥" />
          <StatsCard title="总展位数" :value="stats?.total_booths ?? 0" icon="🏢" />
        </div>

        <div class="card">
          <div class="card-header">
            <h3 class="font-semibold">详细统计</h3>
          </div>
          <div class="card-body">
            <div v-if="!stats || Object.keys(stats).length === 0" class="text-center text-secondary p-6">
              暂无统计数据
            </div>
            <div v-else class="grid grid-cols-1 grid-cols-2 gap-4">
              <div class="info-row">
                <span class="text-secondary">总收入：</span>
                <span class="font-bold">¥{{ (stats?.total_revenue ?? 0).toLocaleString() }}</span>
              </div>
              <div class="info-row">
                <span class="text-secondary">平均每展会报名数：</span>
                <span>{{ stats?.avg_registrations_per_exhibition ?? '-' }}</span>
              </div>
              <div class="info-row">
                <span class="text-secondary">展位占用率：</span>
                <span>{{ stats?.booth_occupancy_rate ? stats.booth_occupancy_rate + '%' : '-' }}</span>
              </div>
              <div class="info-row">
                <span class="text-secondary">采购需求数：</span>
                <span>{{ stats?.total_procurements ?? '-' }}</span>
              </div>
            </div>

            <!-- Per-exhibition breakdown -->
            <div v-if="stats?.exhibitions && stats.exhibitions.length > 0" class="mt-6">
              <h4 class="font-semibold mb-4">各展会统计</h4>
              <div class="card" v-for="ex in stats.exhibitions" :key="ex.id" style="margin-bottom:8px">
                <div class="card-body">
                  <div class="flex justify-between items-center">
                    <h5 class="font-semibold">{{ ex.title }}</h5>
                    <span class="tag" :class="ex.status === 'active' ? 'tag-green' : 'tag-gray'">
                      {{ ex.status }}
                    </span>
                  </div>
                  <div class="flex gap-4 mt-2 text-sm text-secondary">
                    <span>👥 报名：{{ ex.registrations ?? 0 }}</span>
                    <span>🏢 展位：{{ ex.booths ?? 0 }}</span>
                    <span>📦 采购：{{ ex.procurements ?? 0 }}</span>
                    <span v-if="ex.revenue">💰 ¥{{ ex.revenue.toLocaleString() }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.info-row {
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  gap: 12px;
  align-items: center;
}
.info-row:last-child {
  border-bottom: none;
}
</style>
