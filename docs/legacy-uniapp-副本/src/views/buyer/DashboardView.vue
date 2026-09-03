<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import StatsCard from '@/components/StatsCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import ProcurementCard from '@/components/ProcurementCard.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { procurementApi, type Procurement } from '@/api/procurement'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const registeredExhibitions = ref<Exhibition[]>([])
const myProcurements = ref<Procurement[]>([])

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const [regRes, procRes] = await Promise.all([
      exhibitionApi.getRegistrations({ page: 1, page_size: 5 }),
      procurementApi.getMyProcurements({ page: 1, page_size: 5 }),
    ])
    registeredExhibitions.value = regRes.items || regRes.results || regRes.data || []
    myProcurements.value = procRes.items || procRes.results || procRes.data || []
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <h1 class="page-title">🛒 买家中心</h1>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchData">重试</button>
      </div>

      <div v-else>
        <!-- Stats -->
        <div class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-4 mb-6">
          <StatsCard title="已报名展会" :value="registeredExhibitions.length" icon="📋" />
          <StatsCard title="采购需求" :value="myProcurements.length" icon="📦" />
          <StatsCard title="消息" :value="0" icon="📬" />
        </div>

        <!-- Quick Actions -->
        <div class="card mb-6">
          <div class="card-header">
            <h3 class="font-semibold">快捷操作</h3>
          </div>
          <div class="card-body">
            <div class="flex flex-col gap-2">
              <button class="btn btn-outline btn-block" @click="router.push('/exhibitions')">
                🎪 浏览展会市场
              </button>
              <button class="btn btn-outline btn-block" @click="router.push('/buyer/registrations')">
                📋 我报名的展会
              </button>
              <button class="btn btn-outline btn-block" @click="router.push('/buyer/procurements')">
                📦 我的采购需求
              </button>
              <button class="btn btn-primary btn-block" @click="router.push('/buyer/procurements/create')">
                ➕ 发布新采购需求
              </button>
            </div>
          </div>
        </div>

        <!-- Recent Registered Exhibitions -->
        <div class="card mb-6">
          <div class="card-header flex justify-between items-center">
            <h3 class="font-semibold">我报名的展会</h3>
            <button class="btn btn-sm btn-outline" @click="router.push('/buyer/registrations')">查看全部 →</button>
          </div>
          <div class="card-body">
            <div v-if="registeredExhibitions.length === 0" class="text-center text-secondary p-4">
              暂无报名，<router-link to="/exhibitions">去浏览展会</router-link>
            </div>
            <div v-else class="grid grid-cols-1 grid-cols-2 gap-4">
              <ExpoCard
                v-for="ex in registeredExhibitions.slice(0, 4)"
                :key="ex.id"
                :exhibition="ex"
                @click="router.push({ name: 'exhibition-detail', params: { id: ex.id } })"
              />
            </div>
          </div>
        </div>

        <!-- Recent Procurements -->
        <div class="card">
          <div class="card-header flex justify-between items-center">
            <h3 class="font-semibold">我的采购需求</h3>
            <button class="btn btn-sm btn-outline" @click="router.push('/buyer/procurements')">查看全部 →</button>
          </div>
          <div class="card-body">
            <div v-if="myProcurements.length === 0" class="text-center text-secondary p-4">
              暂无采购需求，<router-link to="/buyer/procurements/create">立即发布</router-link>
            </div>
            <div v-else class="grid grid-cols-1 grid-cols-2 gap-4">
              <ProcurementCard
                v-for="proc in myProcurements.slice(0, 4)"
                :key="proc.id"
                :procurement="proc"
                @click="router.push({ name: 'procurement-detail', params: { id: proc.id } })"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
