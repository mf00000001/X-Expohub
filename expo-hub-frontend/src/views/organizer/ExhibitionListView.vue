<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ExpoCard from '@/components/ExpoCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { exhibitionApi, type ExhibitionItem as Exhibition } from '@/api/exhibition'
import { useUserStore } from '@/stores/user'

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
    const userStore = useUserStore()
    const res = await exhibitionApi.getList({ page: currentPage.value, page_size: 9 })
    const all = res.list || res.items || res.results || res.data || []
    // Filter to show only this organizer's exhibitions
    const organizerId = userStore.profile?.id
    exhibitions.value = organizerId ? all.filter((e: any) => e.organizer_id === organizerId) : all
    totalPages.value = Math.ceil((res.total || all.length) / 9) || 1
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载展会列表失败'
  } finally {
    loading.value = false
  }
}

async function publishExhibition(id: number) {
  try {
    await exhibitionApi.publish(id)
    fetchExhibitions()
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '发布失败')
  }
}

async function deleteExhibition(id: number) {
  if (!confirm('确定要删除这个展会吗？此操作不可撤销。')) return
  try {
    await exhibitionApi.remove(id)
    fetchExhibitions()
  } catch (e: any) {
    alert(e.response?.data?.detail || e.message || '删除失败')
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
        <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">我管理的展会</h1>
        <div class="flex gap-2">
          <button class="btn btn-outline btn-sm" @click="router.push('/organizer/dashboard')" style="margin-right:8px">
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

      <div v-else class="exhibition-admin-list">
        <div v-for="exhibition in exhibitions" :key="exhibition.id" class="card card-body admin-exhibition-row">
          <div class="flex justify-between items-start">
            <div class="flex-1 cursor-pointer" @click="goToDetail(exhibition.id)">
              <div class="flex items-center gap-3">
                <img v-if="exhibition.cover_image||exhibition.cover_url" :src="exhibition.cover_image||exhibition.cover_url" style="width:80px;height:60px;object-fit:cover;border-radius:6px" />
                <div>
                  <h3 class="font-semibold text-lg">{{ exhibition.title||exhibition.name }}</h3>
                  <p class="text-sm text-secondary">{{ exhibition.start_date||exhibition.startDate }} ~ {{ exhibition.end_date||exhibition.endDate }}</p>
                  <p class="text-sm text-secondary">{{ exhibition.location||exhibition.venue }}</p>
                  <span class="tag tag-sm" :class="(exhibition.status==='draft'||exhibition.status==='pending')?'tag-warning':'tag-success'">{{ exhibition.status }}</span>
                </div>
              </div>
            </div>
            <div class="flex gap-2" style="flex-shrink:0">
              <button v-if="exhibition.status==='draft'||exhibition.status==='pending'" class="btn btn-success btn-sm" @click.stop="publishExhibition(exhibition.id)">发布</button>
              <button class="btn btn-outline btn-sm" @click.stop="router.push({name:'organizer-exhibition-edit',params:{id:exhibition.id}})">编辑</button>
              <button class="btn btn-danger btn-sm" @click.stop="deleteExhibition(exhibition.id)">删除</button>
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
