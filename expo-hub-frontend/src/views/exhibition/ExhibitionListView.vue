<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ExpoCard from '@/components/ExpoCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'

const PAGE_SIZE_KEY = 'exhibition-list-page-size'
const router = useRouter()
const exhibitions = ref<Exhibition[]>([])
const loading = ref(true)
const searchKeyword = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const total = ref(0)
const pageSize = ref(Number(localStorage.getItem(PAGE_SIZE_KEY)) || 9)

// 后端状态值: draft/pending/published/ongoing/ended/cancelled
const statusOptions = [
  { label: '全部', value: '' },
  { label: '进行中', value: 'ongoing' },
  { label: '已发布', value: 'published' },
  { label: '即将开始', value: 'draft' },
  { label: '已结束', value: 'ended' },
]

async function fetchExhibitions() {
  loading.value = true
  try {
    const res = await exhibitionApi.getList({
      page: currentPage.value,
      page_size: pageSize.value,
      status: statusFilter.value || undefined,
      search: searchKeyword.value || undefined,
    })
    const list = res.list || res.items || res.results || []
    exhibitions.value = list
    total.value = Number((res as any).total ?? list.length) || list.length
    totalPages.value = Number((res as any).total_pages ?? (res as any).totalPages ?? 0)
      || Math.max(1, Math.ceil(total.value / pageSize.value))
  } catch (err) {
    console.error('Failed to load exhibitions:', err)
  } finally {
    loading.value = false
  }
}

onMounted(fetchExhibitions)

function handleSearch(value: string) {
  searchKeyword.value = value
  currentPage.value = 1
  fetchExhibitions()
}

function handleFilter(status: string) {
  statusFilter.value = status
  currentPage.value = 1
  fetchExhibitions()
}

function goToDetail(id: number) {
  router.push({ name: 'exhibition-detail', params: { id } })
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <h1 class="page-title">全部展会</h1>

      <div class="flex gap-4 mb-6 items-center" style="flex-wrap:wrap">
        <div style="flex:1;min-width:200px">
          <SearchBar v-model="searchKeyword" @search="handleSearch" />
        </div>
        <div class="flex gap-2">
          <button
            v-for="opt in statusOptions"
            :key="opt.value"
            :class="['btn btn-sm', statusFilter === opt.value ? 'btn-primary' : 'btn-outline']"
            @click="handleFilter(opt.value)"
          >{{ opt.label }}</button>
        </div>
      </div>

      <LoadingSkeleton v-if="loading" :lines="6" />
      <EmptyState v-else-if="exhibitions.length === 0" message="暂无展会" icon="🎪" />
      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <ExpoCard
          v-for="exhibition in exhibitions"
          :key="exhibition.id"
          :exhibition="exhibition"
          @click="goToDetail(exhibition.id)"
        />
      </div>

      <PaginationBar
        v-if="!loading && exhibitions.length"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :total-pages="totalPages"
        :loading="loading"
        unit="场展会"
        :page-size-options="[9, 18, 36, 72]"
        storage-key="exhibition-list-page-size"
        @change="fetchExhibitions"
      />
    </div>
  </div>
</template>
