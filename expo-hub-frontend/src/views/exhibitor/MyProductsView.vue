<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ProductCard from '@/components/ProductCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { productApi, EXHIBITION_CATEGORIES, type MyProductsSort, type Product } from '@/api/product'

const router = useRouter()
const products = ref<Product[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const PAGE_SIZE_KEY = 'my-products-page-size'
const total = ref(0)
const pageSize = ref(Number(localStorage.getItem(PAGE_SIZE_KEY)) || 9)

// ---- 工具条：搜索 + 品类 / 状态 / 排序 ----
// searchKeyword 是输入框里的值；appliedSearch 是「已确认」的关键词（回车 / 搜索按钮 / 失焦 / 清空后才生效），
// 避免翻页时把还没确认的半截关键词带进请求
const searchKeyword = ref('')
const appliedSearch = ref('')
const categoryFilter = ref('')
const statusFilter = ref('')
const sortBy = ref<string>('newest')

// 状态选项：与后端 Product.status 取值一致（draft / published / offline）
const STATUS_OPTIONS = [
  { value: 'published', label: '上架' },
  { value: 'offline', label: '下架' },
  { value: 'draft', label: '草稿' },
] as const

// 排序选项：值为后端 sort 枚举
const SORT_OPTIONS: { value: MyProductsSort; label: string }[] = [
  { value: 'newest', label: '最新' },
  { value: 'oldest', label: '最早' },
  { value: 'price_desc', label: '价格高→低' },
  { value: 'price_asc', label: '价格低→高' },
]

// 是否处于筛选态（排序不算筛选：无数据时不该提示「没有匹配」）
const hasFilters = computed(
  () => !!(appliedSearch.value || categoryFilter.value || statusFilter.value),
)

// 请求序号：搜索框失焦搜索 + 下拉 watch 可能紧接着各发一次请求，
// 只认最后一次的响应，避免旧响应后到把新结果覆盖掉
let requestSeq = 0

async function fetchProducts() {
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const res = await productApi.getMyProducts({
      page: currentPage.value,
      page_size: pageSize.value,
      // 空值传 undefined（不传），保证「什么都不选」时与改动前的默认行为完全一致
      search: appliedSearch.value || undefined,
      category: categoryFilter.value || undefined,
      status: statusFilter.value || undefined,
      // 下拉的 v-model 是普通字符串，这里收窄回后端枚举类型
      sort: (sortBy.value || undefined) as MyProductsSort | undefined,
    })
    if (seq !== requestSeq) return
    products.value = res.list || res.items || res.results || []
    total.value = Number((res as any).total ?? products.value.length) || products.value.length
    totalPages.value = Number((res as any).totalPages ?? (res as any).total_pages ?? 0)
      || Math.max(1, Math.ceil(total.value / pageSize.value))
  } catch (e: any) {
    if (seq !== requestSeq) return
    error.value = e.response?.data?.detail || e.message || '加载展品列表失败'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

// 搜索确认（回车 / 点搜索按钮 / 失焦 / 清空）：重置到第 1 页重新请求
function handleSearch(value: string) {
  appliedSearch.value = (value || '').trim()
  searchKeyword.value = value
  currentPage.value = 1
  fetchProducts()
}

// 一键清空筛选需要连排序一起复位；用该标记避免 watch 与手动请求重复打两次接口
let suppressFilterWatch = false

// 品类 / 状态 / 排序变化：同样重置到第 1 页
watch(
  [categoryFilter, statusFilter, sortBy],
  () => {
    if (suppressFilterWatch) return
    currentPage.value = 1
    fetchProducts()
  },
  { flush: 'sync' },
)

// 清空全部筛选条件（空态里的「清空筛选」用）
function resetFilters() {
  suppressFilterWatch = true
  searchKeyword.value = ''
  appliedSearch.value = ''
  categoryFilter.value = ''
  statusFilter.value = ''
  sortBy.value = 'newest'
  suppressFilterWatch = false
  currentPage.value = 1
  fetchProducts()
}

onMounted(fetchProducts)

function goToDetail(id: number) {
  router.push({ name: 'product-detail', params: { id } })
}

function goToCreate() {
  router.push({ name: 'exhibitor-product-create' })
}

function goToEdit(id: number) {
  router.push({ name: 'exhibitor-product-edit', params: { id } })
}

async function handleDelete(id: number) {
  const name = products.value.find(p => p.id === id)?.name || `#${id}`
  if (!confirm(`确定删除展品"${name}"？此操作不可恢复。`)) return
  try {
    await productApi.delete(id)
    alert('展品已删除')
    await fetchProducts()
  } catch (e: any) {
    alert(e?.response?.data?.message || e?.response?.data?.detail || '删除失败')
  }
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">我的展品</h1>
        <div class="flex gap-2">
          <button class="btn btn-outline btn-sm" @click="router.push('/exhibitor/dashboard')">
            ← 返回工作台
          </button>
          <button class="btn btn-primary" @click="goToCreate">+ 添加展品</button>
        </div>
      </div>

      <!-- 工具条：搜索（回车/按钮才搜）+ 品类 + 状态 + 排序，任一变化都回到第 1 页 -->
      <div class="product-toolbar">
        <div class="toolbar-search">
          <SearchBar
            v-model="searchKeyword"
            :live="false"
            placeholder="搜索展品名称或描述..."
            @search="handleSearch"
          />
        </div>
        <select v-model="categoryFilter" class="form-select toolbar-select" aria-label="品类筛选">
          <option value="">全部品类</option>
          <option v-for="cat in EXHIBITION_CATEGORIES" :key="cat" :value="cat">{{ cat }}</option>
        </select>
        <select v-model="statusFilter" class="form-select toolbar-select" aria-label="状态筛选">
          <option value="">全部状态</option>
          <option v-for="opt in STATUS_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <select v-model="sortBy" class="form-select toolbar-select" aria-label="排序方式">
          <option v-for="opt in SORT_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchProducts">重试</button>
      </div>

      <!-- 筛选后无结果：给清空筛选的出口 -->
      <EmptyState
        v-else-if="products.length === 0 && hasFilters"
        icon="🔍"
        text="没有匹配的展品"
        show-action
        action-text="清空筛选"
        @action="resetFilters"
      />

      <EmptyState v-else-if="products.length === 0" message="暂未添加展品" icon="📦">
        <button class="btn btn-primary mt-4" @click="goToCreate">立即添加</button>
      </EmptyState>

      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <ProductCard
          v-for="product in products"
          :key="product.id"
          :product="product"
          manageable
          @click="goToDetail(product.id)"
          @manage-edit="goToEdit"
          @manage-delete="handleDelete"
        />
      </div>

      <PaginationBar
        v-if="!loading && products.length"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :total-pages="totalPages"
        :loading="loading"
        unit="件展品"
        :page-size-options="[9, 18, 36, 72]"
        storage-key="my-products-page-size"
        @change="fetchProducts"
      />
    </div>
  </div>
</template>

<style scoped>
/* 工具条：搜索框自适应撑开，三个下拉固定宽度；窄屏自动换行（不依赖全局栅格工具类） */
.product-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
}

.toolbar-search {
  flex: 1 1 280px;
  min-width: 220px;
}

.toolbar-select {
  width: auto;
  min-width: 132px;
}

@media (max-width: 640px) {
  .product-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-select {
    width: 100%;
  }
}
</style>
