<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ExpoCard from '@/components/ExpoCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { exhibitionApi, type ExhibitionItem as Exhibition } from '@/api/exhibition'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const exhibitions = ref<Exhibition[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const PAGE_SIZE_KEY = 'org-exhibitions-page-size'
const total = ref(0)
const pageSize = ref(Number(localStorage.getItem(PAGE_SIZE_KEY)) || 9)

async function fetchExhibitions() {
  loading.value = true
  error.value = ''
  try {
    const userStore = useUserStore()
    const organizerId = userStore.profile?.id
    // 后端已支持 organizer_id 过滤（此前该参数被忽略，只能靠前端过滤 → 分页总数失真）
    const req: any = { page: currentPage.value, page_size: pageSize.value }
    const res = organizerId
      ? await exhibitionApi.getMyExhibitions(organizerId, req)
      : await exhibitionApi.getList(req)
    const all = res.list || res.items || res.results || res.data || []
    // 兼容未升级的后端：若服务端未按主办方过滤，退回前端过滤并退化为单页
    exhibitions.value = organizerId ? all.filter((e: any) => e.organizer_id === organizerId) : all
    const serverFiltered = exhibitions.value.length === all.length
    total.value = serverFiltered
      ? (Number((res as any).total ?? all.length) || all.length)
      : exhibitions.value.length
    totalPages.value = serverFiltered
      ? (Number((res as any).totalPages ?? (res as any).total_pages ?? 0)
         || Math.max(1, Math.ceil(total.value / pageSize.value)))
      : 1
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
              <button class="btn btn-outline btn-sm" @click.stop="router.push('/organizer/exhibitions/'+exhibition.id+'/registrations')">登记</button>
              <button class="btn btn-danger btn-sm" @click.stop="deleteExhibition(exhibition.id)">删除</button>
            </div>
          </div>
        </div>
      </div>

      <PaginationBar
        v-if="!loading && exhibitions.length"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :total-pages="totalPages"
        :loading="loading"
        unit="个展会"
        :page-size-options="[9, 18, 36, 72]"
        storage-key="org-exhibitions-page-size"
        @change="fetchExhibitions"
      />
    </div>
  </div>
</template>
