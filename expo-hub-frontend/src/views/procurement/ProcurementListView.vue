<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ProcurementCard from '@/components/ProcurementCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { procurementApi, type Procurement } from '@/api/procurement'
import { EXHIBITION_CATEGORIES } from '@/api/product'

const router = useRouter()
const procurements = ref<Procurement[]>([])
const loading = ref(true)
const searchKeyword = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
// V3.3: 分类筛选
const activeCategory = ref('全部')

async function fetchProcurements() {
  loading.value = true
  try {
    const res = await procurementApi.getList({
      page: currentPage.value,
      page_size: 12,
      search: searchKeyword.value || undefined,
      category: activeCategory.value === '全部' ? undefined : activeCategory.value,
    })
    procurements.value = (res as any).list || (res as any).items || (res as any).results || []
    totalPages.value = (res as any).total_pages || Math.ceil(((res as any).total || 0) / 12) || 1
  } catch (err) {
    console.error('Failed to load procurements:', err)
  } finally {
    loading.value = false
  }
}

onMounted(fetchProcurements)

function handleSearch(value: string) {
  searchKeyword.value = value
  currentPage.value = 1
  fetchProcurements()
}

function selectCategory(cat: string) {
  activeCategory.value = cat
  currentPage.value = 1
  fetchProcurements()
}

function goToDetail(id: number) {
  router.push({ name: 'procurement-detail', params: { id } })
}

function changePage(page: number) {
  currentPage.value = page
  fetchProcurements()
  window.scrollTo(0, 0)
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <h1 class="page-title">采购需求</h1>
      <div class="mb-6" style="max-width:500px">
        <SearchBar v-model="searchKeyword" @search="handleSearch" />
      </div>

      <!-- V3.3: 分类筛选 -->
      <div class="cat-chips">
        <button class="chip" :class="{ active: activeCategory === '全部' }" @click="selectCategory('全部')">全部</button>
        <button
          v-for="cat in EXHIBITION_CATEGORIES"
          :key="cat"
          class="chip"
          :class="{ active: activeCategory === cat }"
          @click="selectCategory(cat)"
        >{{ cat }}</button>
      </div>

      <LoadingSkeleton v-if="loading" :lines="6" />
      <EmptyState v-else-if="procurements.length === 0" message="暂无采购需求" icon="📋" />
      <div v-else class="grid grid-cols-1 grid-cols-2 gap-4">
        <ProcurementCard
          v-for="procurement in procurements"
          :key="procurement.id"
          :procurement="procurement"
          @click="goToDetail(procurement.id)"
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

<style scoped>
.cat-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
.chip {
  border: 1px solid #e2e8f0; background: #fff; border-radius: 999px;
  padding: 5px 14px; font-size: 13px; color: #475569; cursor: pointer; transition: all .2s;
}
.chip:hover { border-color: #93c5fd; color: #2563eb; }
.chip.active { background: #2563eb; border-color: #2563eb; color: #fff; font-weight: 500; }
</style>