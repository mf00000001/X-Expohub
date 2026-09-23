<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { boothApi, type Booth } from '@/api/booth'

const router = useRouter()
const booths = ref<Booth[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const PAGE_SIZE_KEY = 'my-booths-page-size'
const total = ref(0)
const pageSize = ref(Number(localStorage.getItem(PAGE_SIZE_KEY)) || 9)

async function fetchBooths() {
  loading.value = true
  error.value = ''
  try {
    const res = await boothApi.getMyBooths({
      page: currentPage.value,
      page_size: pageSize.value,
    })
    booths.value = res.list || res.items || res.results || []
    total.value = Number((res as any).total ?? booths.value.length) || booths.value.length
    totalPages.value = Number((res as any).totalPages ?? (res as any).total_pages ?? 0)
      || Math.max(1, Math.ceil(total.value / pageSize.value))
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载展位失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchBooths)

function goToDetail(id: number) {
  router.push({ name: 'booth-detail', params: { id } })
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">我的展位</h1>
        <button class="btn btn-outline btn-sm" @click="router.push('/exhibitor/dashboard')">
          ← 返回工作台
        </button>
      </div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchBooths">重试</button>
      </div>

      <EmptyState v-else-if="booths.length === 0" message="暂未申请展位" icon="🏢" />

      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <div
          v-for="booth in booths"
          :key="booth.id"
          class="card cursor-pointer"
          @click="goToDetail(booth.id)"
        >
          <div class="card-body">
            <div class="flex justify-between items-center mb-2">
              <h3 class="font-semibold text-lg">
                {{ booth.company_name || booth.exhibitor_name || '展位' }}
              </h3>
              <StatusTag :status="booth.status" />
            </div>
            <p class="text-sm text-secondary mb-1">
              展位号：<strong>{{ booth.booth_number }}</strong>
            </p>
            <p v-if="booth.size" class="text-sm text-secondary mb-1">
              面积：{{ booth.size }}
            </p>
            <p v-if="booth.location_area" class="text-sm text-secondary mb-1">
              区域：{{ booth.location_area }}
            </p>
            <p v-if="booth.price" class="text-sm text-secondary">
              价格：¥{{ booth.price }}
            </p>
          </div>
        </div>
      </div>

      <PaginationBar
        v-if="!loading && booths.length"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :total-pages="totalPages"
        :loading="loading"
        unit="个展位"
        :page-size-options="[9, 18, 36, 72]"
        storage-key="my-booths-page-size"
        @change="fetchBooths"
      />
    </div>
  </div>
</template>

<style scoped>
.cursor-pointer {
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.cursor-pointer:hover {
  box-shadow: var(--shadow-md);
}
</style>
