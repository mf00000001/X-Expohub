<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ProcurementCard from '@/components/ProcurementCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { procurementApi, type Procurement } from '@/api/procurement'

const router = useRouter()
const procurements = ref<Procurement[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

async function fetchProcurements() {
  loading.value = true
  error.value = ''
  try {
    const res = await procurementApi.getMyProcurements({
      page: currentPage.value,
      page_size: 9,
    })
    procurements.value = (res as any).list || (res as any).items || (res as any).results || []
    totalPages.value = (res as any).total_pages || Math.ceil(((res as any).total || 0) / 9) || 1
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载采购需求失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchProcurements)

function goToDetail(id: number) {
  router.push({ name: 'procurement-detail', params: { id } })
}

function goToCreate() {
  router.push({ name: 'visitor-procurement-create' })
}

function changePage(page: number) {
  currentPage.value = page
  fetchProcurements()
  window.scrollTo(0, 0)
}

function canCancel(p: any): boolean {
  return ['pending', 'open', 'published', 'matched'].includes(p.status)
}

async function handleCancel(item: any) {
  if (!confirm(`确定取消采购需求"${item.title}"？取消后展商将无法继续应标。`)) return
  try {
    await procurementApi.cancel(item.id)
    alert('✅ 采购需求已取消')
    await fetchProcurements()
  } catch (e: any) {
    alert(e?.response?.data?.message || '取消失败，请稍后再试')
  }
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">我的采购需求</h1>
        <button class="btn btn-primary" @click="goToCreate">+ 发布采购</button>
      </div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchProcurements">重试</button>
      </div>

      <EmptyState v-else-if="procurements.length === 0" message="暂未发布采购需求" icon="📦">
        <button class="btn btn-primary mt-4" @click="goToCreate">立即发布</button>
      </EmptyState>

      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <div v-for="item in procurements" :key="item.id" class="proc-wrap">
          <ProcurementCard
            :procurement="item"
            @click="goToDetail(item.id)"
          />
          <button v-if="canCancel(item)" class="btn btn-sm proc-cancel" @click="handleCancel(item)">✖ 取消需求</button>
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

<style scoped>
.proc-wrap { display: flex; flex-direction: column; gap: 6px; }
.proc-cancel { align-self: flex-end; background: #fff; color: #dc2626; border: 1px solid #fecaca; }
.proc-cancel:hover { background: #fef2f2; }
</style>
