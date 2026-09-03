<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import StatsCard from '@/components/StatsCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import { getDashboardStats } from '@/api/dashboard'

const router = useRouter()
const stats = ref<any>(null)
const loading = ref(true)
const error = ref('')

async function fetchStats() {
  loading.value = true
  error.value = ''
  try {
    const data = await getDashboardStats()
    stats.value = data
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载仪表盘数据失败'
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
      <h1 class="page-title">展商工作台</h1>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchStats">重试</button>
      </div>

      <div v-else>
        <div class="grid grid-cols-1 grid-cols-2 grid-cols-4 gap-4 mb-6">
          <StatsCard title="我的展位" :value="stats?.booth_count ?? 0" icon="🏢" />
          <StatsCard title="我的展品" :value="stats?.product_count ?? 0" icon="📦" />
          <StatsCard title="采购匹配" :value="stats?.match_count ?? 0" icon="🤝" />
          <StatsCard title="报名展会" :value="stats?.registration_count ?? 0" icon="📋" />
        </div>

        <div class="grid grid-cols-1 grid-cols-2 gap-6">
          <div class="card">
            <div class="card-header">
              <h3 class="font-semibold">快捷操作</h3>
            </div>
            <div class="card-body">
              <div class="flex flex-col gap-2">
                <button class="btn btn-outline btn-block" @click="router.push('/exhibitor/booths')">
                  🏢 管理我的展位
                </button>
                <button class="btn btn-outline btn-block" @click="router.push('/exhibitor/products')">
                  📦 管理我的展品
                </button>
                <button class="btn btn-outline btn-block" @click="router.push('/exhibitor/products/create')">
                  ➕ 添加新展品
                </button>
                <button class="btn btn-outline btn-block" @click="router.push('/exhibitor/procurement-matches')">
                  🤝 查看采购匹配
                </button>
                <button class="btn btn-outline btn-block" @click="router.push('/visitor/registrations')">
                  📋 我的报名
                </button>
              </div>
            </div>
          </div>

          <div class="card" v-if="stats">
            <div class="card-header">
              <h3 class="font-semibold">概览信息</h3>
            </div>
            <div class="card-body">
              <div class="info-row" v-if="stats?.latest_booth">
                <span class="text-secondary">最新展位：</span>
                <span>{{ stats.latest_booth }}</span>
              </div>
              <div class="info-row" v-if="stats?.latest_product">
                <span class="text-secondary">最新展品：</span>
                <span>{{ stats.latest_product }}</span>
              </div>
              <div class="info-row" v-if="stats?.upcoming_exhibition">
                <span class="text-secondary">近期展会：</span>
                <span>{{ stats.upcoming_exhibition }}</span>
              </div>
              <p v-if="!stats?.latest_booth && !stats?.latest_product" class="text-secondary text-sm">
                暂无数据，开始探索吧！
              </p>
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
