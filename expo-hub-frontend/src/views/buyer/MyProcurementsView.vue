<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ProcurementCard from '@/components/ProcurementCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { procurementApi, type Procurement } from '@/api/procurement'

const router = useRouter()
const procurements = ref<Procurement[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const PAGE_SIZE_KEY = 'my-procurements-page-size'
const total = ref(0)
const pageSize = ref(Number(localStorage.getItem(PAGE_SIZE_KEY)) || 9)

async function fetchProcurements() {
  loading.value = true
  error.value = ''
  try {
    const res = await procurementApi.getMyProcurements({
      page: currentPage.value,
      page_size: pageSize.value,
    })
    procurements.value = res.list || res.items || res.results || []
    total.value = Number((res as any).total ?? procurements.value.length) || procurements.value.length
    totalPages.value = Number((res as any).totalPages ?? (res as any).total_pages ?? 0)
      || Math.max(1, Math.ceil(total.value / pageSize.value))
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载采购需求失败'
  } finally {
    loading.value = false
  }
}

// 概览统计（当前页内）：待处理应标的需求 / 已完结
const withBids = computed(() => procurements.value.filter((x: any) => (x.match_count || 0) > 0 && ['pending', 'matched'].includes(x.status)).length)
const finished = computed(() => procurements.value.filter((x: any) => ['completed', 'cancelled'].includes(x.status)).length)

onMounted(fetchProcurements)

function goToDetail(id: number) {
  router.push({ name: 'procurement-detail', params: { id } })
}

function goToCreate() {
  router.push({ name: 'buyer-procurement-create' })
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
        <div class="flex gap-2">
          <button class="btn btn-outline btn-sm" @click="router.push('/buyer/dashboard')">
            ← 返回买家中心
          </button>
          <button class="btn btn-primary" @click="goToCreate">+ 发布采购</button>
        </div>
      </div>

      <div class="summary-row" style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">
        <span class="tag tag-success" v-if="withBids>0">🔔 {{ withBids }} 条有应标待处理 →</span>
        <span class="tag tag-info" v-if="finished>0">✅ {{ finished }} 条已完结</span>
        <span class="tag tag-warning" v-if="!loading && procurements.length===0">暂无需求，发布后会有展商应标</span>
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

      <PaginationBar
        v-if="!loading && procurements.length"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :total-pages="totalPages"
        :loading="loading"
        unit="条需求"
        :page-size-options="[9, 18, 36, 72]"
        storage-key="my-procurements-page-size"
        @change="fetchProcurements"
      />
    </div>
  </div>
</template>

<style scoped>
.proc-wrap { display: flex; flex-direction: column; gap: 6px; }
.proc-cancel { align-self: flex-end; background: #fff; color: #dc2626; border: 1px solid #fecaca; }
.proc-cancel:hover { background: #fef2f2; }
</style>
