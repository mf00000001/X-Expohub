<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import ProcurementCard from '@/components/ProcurementCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { procurementApi, type Procurement } from '@/api/procurement'
import http from '@/api/index'

const router = useRouter()
const procurements = ref<Procurement[]>([])
const loading = ref(true)
const error = ref('')
const matchingId = ref<number | null>(null)
const actionMsg = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

async function fetchProcurements() {
  loading.value = true
  error.value = ''
  try {
    const res = await procurementApi.getList({
      page: currentPage.value,
      page_size: 9,
    })
    procurements.value = res.items || res.results || res.data || []
    totalPages.value = res.total_pages || Math.ceil((res.total || 0) / 9) || 1
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载采购需求失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchProcurements)

async function handleMatch(procurementId: number) {
  matchingId.value = procurementId
  actionMsg.value = ''
  try {
    await http.post('/api/v1/procurements/matches', { procurement_id: procurementId })
    actionMsg.value = '响应成功！已向采购方发送匹配通知'
  } catch (e: any) {
    actionMsg.value = e.response?.data?.detail || e.message || '匹配失败'
  } finally {
    matchingId.value = null
  }
}

function goToDetail(id: number) {
  router.push({ name: 'procurement-detail', params: { id } })
}

function changePage(page: number) {
  currentPage.value = page
  fetchProcurements()
  window.scrollTo(0, 0)
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">采购需求匹配</h1>
        <button class="btn btn-outline btn-sm" @click="router.push('/exhibitor/dashboard')">
          ← 返回工作台
        </button>
      </div>

      <div v-if="actionMsg" class="tag tag-green mb-4 p-3" style="display:block;">{{ actionMsg }}</div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchProcurements">重试</button>
      </div>

      <EmptyState v-else-if="procurements.length === 0" message="暂无可匹配的采购需求" icon="🤝" />

      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <div
          v-for="item in procurements"
          :key="item.id"
          class="card"
        >
          <ProcurementCard
            :procurement="item"
            @click="goToDetail(item.id)"
          />
          <div class="card-footer">
            <button
              class="btn btn-primary btn-sm btn-block"
              :disabled="matchingId === item.id"
              @click.stop="handleMatch(item.id)"
            >
              {{ matchingId === item.id ? '响应中...' : '🤝 响应此采购' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="totalPages > 1" class="pagination">
        <button :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
        <button
          v-for="page in totalPages"
          :key="page"
          :class="{ active: page === currentPage }"
          @click="changePage(page)"
        >{{ page }}</button>
        <button :disabled="currentPage >= totalPages" @click="changePage(currentPage + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>
