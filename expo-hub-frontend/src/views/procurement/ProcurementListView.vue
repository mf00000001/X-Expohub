<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ProcurementCard from '@/components/ProcurementCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { procurementApi, type Procurement } from '@/api/procurement'
import { EXHIBITION_CATEGORIES } from '@/api/product'

const PAGE_SIZE_KEY = 'procurement-list-page-size'
const router = useRouter()
const procurements = ref<Procurement[]>([])
const loading = ref(true)
const searchKeyword = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const total = ref(0)
// 此前固定 50 条/页看不到总量；改为可选并记住用户偏好
const pageSize = ref(Number(localStorage.getItem(PAGE_SIZE_KEY)) || 24)
// V3.3: 分类筛选
const activeCategory = ref('全部')

async function fetchProcurements() {
  loading.value = true
  try {
    const res = await procurementApi.getList({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchKeyword.value || undefined,
      category: activeCategory.value === '全部' ? undefined : activeCategory.value,
    })
    const list = (res as any).list || (res as any).items || (res as any).results || []
    procurements.value = list
    total.value = Number((res as any).total ?? list.length) || list.length
    totalPages.value = Number((res as any).total_pages ?? (res as any).totalPages ?? 0)
      || Math.max(1, Math.ceil(total.value / pageSize.value))
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
</script>

<template>
  <div class="page-container">
    <!-- 微展位风格页面头 -->
    <div class="page-header">
      <h2>📋 采购需求</h2>
      <p style="font-size:13px;color:var(--color-text-secondary);margin-top:4px">发现优质采购需求 · 分类筛选 · 对接展商</p>
    </div>

    <div style="margin-bottom:16px;max-width:400px">
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
    <div v-else class="mb-grid">
      <p v-if="activeCategory !== '全部'" style="grid-column:1/-1;font-size:13px;color:var(--color-text-secondary);margin-bottom:4px">
        分类"{{ activeCategory }}"的结果（共 {{ total }} 条）
      </p>
      <ProcurementCard
        v-for="procurement in procurements"
        :key="procurement.id"
        :procurement="procurement"
        @click="goToDetail(procurement.id)"
      />
    </div>

    <PaginationBar
      v-if="!loading && procurements.length"
      v-model:page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      :total-pages="totalPages"
      :loading="loading"
      unit="条需求"
      :page-size-options="[12, 24, 48, 96]"
      storage-key="procurement-list-page-size"
      @change="fetchProcurements"
    />
  </div>
</template>


<style scoped>
.page-container { max-width: 1200px; margin: 0 auto; padding: 20px 16px; }
.page-header { margin-bottom: 18px; }
.page-header h2 { font-size: 20px; font-weight: 700; margin: 0; }

/* 分类筛选 */
.cat-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
.chip {
  border: 1px solid #e2e8f0; background: #fff; border-radius: 999px;
  padding: 5px 14px; font-size: 13px; color: #475569; cursor: pointer; transition: all .2s;
}
.chip:hover { border-color: #93c5fd; color: #2563eb; }
.chip.active { background: #2563eb; border-color: #2563eb; color: #fff; font-weight: 500; }

/* 微展位风格卡片网格 */
.mb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
</style>
