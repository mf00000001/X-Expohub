<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'

const router = useRouter()
const registrations = ref<Exhibition[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

async function fetchRegistrations() {
  loading.value = true
  error.value = ''
  try {
    const res = await exhibitionApi.getRegistrations({
      page: currentPage.value,
      page_size: 9,
    })
    registrations.value = res.items || res.results || res.data || []
    totalPages.value = res.total_pages || Math.ceil((res.total || 0) / 9) || 1
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载报名记录失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchRegistrations)

function goToExhibition(id: number) {
  router.push({ name: 'exhibition-detail', params: { id } })
}

function goToMarket() {
  router.push('/exhibitions')
}

function changePage(page: number) {
  currentPage.value = page
  fetchRegistrations()
  window.scrollTo(0, 0)
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">我报名的展会</h1>
        <div class="flex gap-2">
          <button class="btn btn-outline btn-sm" @click="router.push('/buyer/dashboard')">
            ← 返回买家中心
          </button>
          <button class="btn btn-primary" @click="goToMarket">浏览展会市场</button>
        </div>
      </div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchRegistrations">重试</button>
      </div>

      <EmptyState v-else-if="registrations.length === 0" message="暂未报名任何展会" icon="📋">
        <button class="btn btn-primary mt-4" @click="goToMarket">去展会市场看看</button>
      </EmptyState>

      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <ExpoCard
          v-for="ex in registrations"
          :key="ex.id"
          :exhibition="ex"
          @click="goToExhibition(ex.id)"
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
