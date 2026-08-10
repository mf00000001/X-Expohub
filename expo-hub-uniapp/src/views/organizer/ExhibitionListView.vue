<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import http from '@/api/index'
import type { Exhibition } from '@/api/exhibition'

const router = useRouter()
const exhibitions = ref<Exhibition[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

async function fetchExhibitions() {
  loading.value = true
  error.value = ''
  try {
    const res = await http.get('/api/v1/exhibitions/organizer/list', {
      params: { page: currentPage.value, page_size: 9 },
    })
    const data = res.data
    exhibitions.value = data.items || data.results || data.data || []
    totalPages.value = data.total_pages || Math.ceil((data.total || 0) / 9) || 1
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载展会列表失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchExhibitions)

function goToDetail(id: number) {
  router.push({ name: 'exhibition-detail', params: { id } })
}

function goToCreate() {
  router.push({ name: 'organizer-exhibition-create' })
}

function changePage(page: number) {
  currentPage.value = page
  fetchExhibitions()
  window.scrollTo(0, 0)
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">我管理的展会</h1>
        <div class="flex gap-2">
          <button class="btn btn-outline btn-sm" @click="router.push('/organizer/dashboard')">
            ← 返回后台
          </button>
          <button class="btn btn-primary" @click="goToCreate">+ 创建展会</button>
        </div>
      </div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchExhibitions">重试</button>
      </div>

      <EmptyState v-else-if="exhibitions.length === 0" message="暂无管理的展会" icon="🎪">
        <button class="btn btn-primary mt-4" @click="goToCreate">创建第一个展会</button>
      </EmptyState>

      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <ExpoCard
          v-for="exhibition in exhibitions"
          :key="exhibition.id"
          :exhibition="exhibition"
          @click="goToDetail(exhibition.id)"
        />
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
