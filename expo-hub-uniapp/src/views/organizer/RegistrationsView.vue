<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import http from '@/api/index'

interface Registration {
  id: number
  exhibition_id: number
  exhibition_title?: string
  user_id?: number
  user_name?: string
  user_email?: string
  user_company?: string
  status: string
  registered_at?: string
  notes?: string
}

const router = useRouter()
const registrations = ref<Registration[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

// We'll use a query param or let the user pick an exhibition
const exhibitionId = ref('')

async function fetchRegistrations() {
  if (!exhibitionId.value) {
    // If no specific exhibition, try a general endpoint
    loading.value = true
    error.value = ''
    try {
      // Fallback: use exhibitions/registrations from exhibitionApi
      const { exhibitionApi } = await import('@/api/exhibition')
      const res = await exhibitionApi.getRegistrations({
        page: currentPage.value,
        page_size: 20,
      })
      registrations.value = res.items || res.results || res.data || []
      totalPages.value = res.total_pages || Math.ceil((res.total || 0) / 20) || 1
    } catch (e: any) {
      error.value = e.response?.data?.detail || e.message || '加载报名列表失败'
    } finally {
      loading.value = false
    }
    return
  }

  loading.value = true
  error.value = ''
  try {
    const res = await http.get(`/api/v1/exhibitions/${exhibitionId.value}/registrations`, {
      params: { page: currentPage.value, page_size: 20 },
    })
    const data = res.data
    registrations.value = data.items || data.results || data.data || []
    totalPages.value = data.total_pages || Math.ceil((data.total || 0) / 20) || 1
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载报名列表失败'
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
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">报名管理</h1>
        <button class="btn btn-outline btn-sm" @click="router.push('/organizer/dashboard')">
          ← 返回后台
        </button>
      </div>

      <div class="card mb-4">
        <div class="card-body">
          <div class="form-group" style="margin-bottom:0">
            <label class="form-label">按展会筛选</label>
            <div class="flex gap-2">
              <input
                v-model="exhibitionId"
                class="form-input"
                type="number"
                placeholder="输入展会 ID"
                style="max-width:200px"
              />
              <button class="btn btn-primary btn-sm" @click="fetchRegistrations">查询</button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchRegistrations">重试</button>
      </div>

      <EmptyState v-else-if="registrations.length === 0" message="暂无报名记录" icon="👥" />

      <div v-else>
        <div class="card" v-for="reg in registrations" :key="reg.id" style="margin-bottom:8px">
          <div class="card-body">
            <div class="flex justify-between items-center">
              <div>
                <h4 class="font-semibold">{{ reg.user_name || '未知用户' }}</h4>
                <p class="text-sm text-secondary">
                  {{ reg.user_email || '' }}
                  <span v-if="reg.user_company"> · {{ reg.user_company }}</span>
                </p>
                <p class="text-sm text-secondary mt-1">
                  展会：{{ reg.exhibition_title || `ID: ${reg.exhibition_id}` }}
                </p>
              </div>
              <div class="text-right">
                <StatusTag :status="reg.status" />
                <p v-if="reg.registered_at" class="text-sm text-secondary mt-1">
                  {{ reg.registered_at }}
                </p>
              </div>
            </div>
            <p v-if="reg.notes" class="text-sm text-secondary mt-2">
              备注：{{ reg.notes }}
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
