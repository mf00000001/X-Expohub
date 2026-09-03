<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import http from '@/api/index'

interface Registration {
  id: number
  exhibition_id: number
  exhibition_title?: string
  exhibition_cover?: string
  exhibition_start_date?: string
  exhibition_end_date?: string
  exhibition_location?: string
  exhibition_status?: string
  status: string
  registered_at?: string
}

const router = useRouter()
const registrations = ref<Registration[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

async function fetchRegistrations() {
  loading.value = true
  error.value = ''
  try {
    const res = await http.get('/api/v1/registrations/my', {
      params: { page: currentPage.value, page_size: 9 },
    })
    const data = res.data
    registrations.value = data.items || data.results || data.data || []
    totalPages.value = data.total_pages || Math.ceil((data.total || 0) / 9) || 1
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
      <h1 class="page-title">我的报名</h1>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchRegistrations">重试</button>
      </div>

      <EmptyState v-else-if="registrations.length === 0" message="暂未报名任何展会" icon="📋" />

      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <div
          v-for="reg in registrations"
          :key="reg.id"
          class="card cursor-pointer"
          @click="goToExhibition(reg.exhibition_id)"
        >
          <div v-if="reg.exhibition_cover" class="card-image">
            <img :src="reg.exhibition_cover" :alt="reg.exhibition_title" />
          </div>
          <div class="card-body">
            <div class="flex justify-between items-center mb-2">
              <h3 class="font-semibold text-lg">{{ reg.exhibition_title || '未命名展会' }}</h3>
              <StatusTag :status="reg.status" />
            </div>
            <p v-if="reg.exhibition_location" class="text-sm text-secondary mb-2">
              📍 {{ reg.exhibition_location }}
            </p>
            <p v-if="reg.exhibition_start_date" class="text-sm text-secondary">
              📅 {{ reg.exhibition_start_date }} ~ {{ reg.exhibition_end_date }}
            </p>
            <p v-if="reg.registered_at" class="text-sm text-secondary mt-2">
              报名时间：{{ reg.registered_at }}
            </p>
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

<style scoped>
.cursor-pointer {
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.cursor-pointer:hover {
  box-shadow: var(--shadow-md);
}
.card-image {
  width: 100%;
  height: 160px;
  overflow: hidden;
}
.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
