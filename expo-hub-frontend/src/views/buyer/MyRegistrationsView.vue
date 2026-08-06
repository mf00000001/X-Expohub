<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { registrationApi, type RegistrationItem } from '@/api/registration'
import { formatDate } from '@/utils/format'

const router = useRouter()
const registrations = ref<RegistrationItem[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = 9

async function fetchRegistrations() {
  loading.value = true
  error.value = ''
  try {
    const res = await registrationApi.getMyRegistrations({
      page: currentPage.value,
      page_size: pageSize,
    })
    registrations.value = res.list
    totalPages.value = res.totalPages
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载报名记录失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchRegistrations)

function changePage(page: number) {
  currentPage.value = page
  fetchRegistrations()
  window.scrollTo(0, 0)
}

function goToExhibition(id: number) {
  router.push({ name: 'exhibition-detail', params: { id } })
}

function goToMarket() {
  router.push('/exhibitions')
}
</script>

<template>
  <div>
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
        <div
          v-for="reg in registrations"
          :key="reg.id"
          class="card cursor-pointer"
          @click="goToExhibition(reg.exhibition_id)"
        >
          <div v-if="reg.exhibition?.cover_image" class="card-image">
            <img :src="reg.exhibition.cover_image" :alt="reg.exhibition.title" />
          </div>
          <div class="card-body">
            <div class="flex justify-between items-start mb-2">
              <h3 class="font-semibold text-lg">{{ reg.exhibition?.title || '未命名展会' }}</h3>
              <StatusTag :status="reg.is_registered ? 'confirmed' : 'cancelled'" size="sm" />
            </div>
            <p v-if="reg.exhibition?.location" class="text-sm text-secondary mb-2">
              📍 {{ reg.exhibition.location }}
            </p>
            <p v-if="reg.exhibition?.start_date" class="text-sm text-secondary">
              📅 {{ formatDate(reg.exhibition.start_date) }} ~ {{ formatDate(reg.exhibition.end_date) }}
            </p>
            <div class="flex justify-between items-center mt-3">
              <p class="text-sm text-secondary">
                报名时间：{{ formatDate(reg.created_at) }}
              </p>
              <span v-if="reg.ticket_code" class="tag tag-primary" style="font-size:11px">
                🎫 {{ reg.ticket_code }}
              </span>
            </div>
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
