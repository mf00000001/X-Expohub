<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import StatusTag from '@/components/StatusTag.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { boothApi, type Booth } from '@/api/booth'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const exhibition = ref<Exhibition | null>(null)
const booths = ref<Booth[]>([])
const loading = ref(true)
const registered = ref(false)

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const [expRes, boothRes] = await Promise.all([
      exhibitionApi.getById(id),
      boothApi.getList({ exhibition_id: id, page: 1, page_size: 50 }),
    ])
    exhibition.value = expRes
    booths.value = boothRes.items || boothRes.results || boothRes.data || []
  } catch (err) {
    console.error('Failed to load exhibition detail:', err)
  } finally {
    loading.value = false
  }
})

async function handleRegister() {
  if (!userStore.isLoggedIn) {
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  try {
    if (exhibition.value) {
      await exhibitionApi.register(exhibition.value.id)
      registered.value = true
      showToast('报名成功！')
    }
  } catch (err: any) {
    showToast(err?.response?.data?.detail || err?.response?.data?.message || '报名失败', 'error')
  }
}

function showToast(message: string, type: 'success' | 'error' = 'success') {
  const toast = document.createElement('div')
  toast.className = `toast toast-${type}`
  toast.textContent = message
  document.body.appendChild(toast)
  setTimeout(() => toast.remove(), 3000)
}

function goToBooth(id: number) {
  router.push({ name: 'booth-detail', params: { id } })
}

// 后端状态: draft/pending/published/ongoing/ended/cancelled
// 可报名的状态: published(已发布), ongoing(进行中)
function canRegister(status: string): boolean {
  return status === 'published' || status === 'ongoing'
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper" v-if="loading">
      <LoadingSkeleton :lines="8" />
    </div>
    <div v-else-if="!exhibition" class="container page-wrapper">
      <p>展会不存在</p>
    </div>
    <div v-else class="container page-wrapper">
      <div class="breadcrumb">
        <router-link to="/">首页</router-link>
        <span>/</span>
        <router-link to="/exhibitions">展会</router-link>
        <span>/</span>
        <span>{{ exhibition.title }}</span>
      </div>

      <div class="card">
        <div class="exhibition-cover" v-if="exhibition.cover_image">
          <img :src="exhibition.cover_image" :alt="exhibition.title" />
        </div>
        <div class="card-body">
          <div class="flex justify-between items-start mb-4">
            <h1 class="text-2xl font-bold">{{ exhibition.title }}</h1>
            <StatusTag :status="exhibition.status" />
          </div>
          <div class="flex gap-6 text-sm text-secondary mb-4" style="flex-wrap:wrap">
            <span>📅 {{ exhibition.start_date }} ~ {{ exhibition.end_date }}</span>
            <span>📍 {{ exhibition.location }}</span>
            <span v-if="exhibition.organizer_name">👤 {{ exhibition.organizer_name }}</span>
          </div>
          <p class="text-secondary" style="line-height:1.8;white-space:pre-wrap;">{{ exhibition.description }}</p>
          <div class="mt-6">
            <button
              v-if="canRegister(exhibition.status)"
              class="btn btn-primary"
              @click="handleRegister"
            >
              {{ registered ? '已报名 ✓' : '立即报名' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Booths section -->
      <div class="mt-6">
        <h2 class="text-xl font-bold mb-4">展位列表</h2>
        <div v-if="booths.length === 0" class="text-secondary text-sm">暂无展位</div>
        <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-4">
          <div
            v-for="booth in booths"
            :key="booth.id"
            class="card card-body cursor-pointer"
            style="cursor:pointer"
            @click="goToBooth(booth.id)"
          >
            <div class="flex justify-between items-center">
              <span class="font-semibold">{{ booth.booth_number }}</span>
              <StatusTag :status="booth.status" />
            </div>
            <p class="text-sm text-secondary mt-2" v-if="booth.company_name">{{ booth.company_name }}</p>
            <p class="text-sm text-secondary" v-if="booth.size">面积: {{ booth.size }}</p>
            <p class="text-sm text-secondary" v-if="booth.location_area">区域: {{ booth.location_area }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.exhibition-cover {
  height: 300px;
  overflow: hidden;
}
.exhibition-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
