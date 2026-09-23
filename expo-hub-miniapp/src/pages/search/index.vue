<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { onLoad, onReachBottom } from '@dcloudio/uni-app'
import SearchBar from '@/components/SearchBar.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import ProductCard from '@/components/ProductCard.vue'
import ProcurementCard from '@/components/ProcurementCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { productApi, type Product } from '@/api/product'
import { procurementApi, type Procurement } from '@/api/procurement'
import type { PageResult } from '@/utils/request'

type TabKey = 'exhibitions' | 'products' | 'procurements'

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'exhibitions', label: '展会' },
  { key: 'products', label: '产品' },
  { key: 'procurements', label: '采购' },
]

const PAGE_SIZE = 10

const activeTab = ref<TabKey>('exhibitions')
const searchKeyword = ref('')
const searched = ref(false)
const loading = ref(false)
const loadingMore = ref(false)

const exhibitions = ref<Exhibition[]>([])
const products = ref<Product[]>([])
const procurements = ref<Procurement[]>([])

interface TabState {
  page: number
  total: number
  hasMore: boolean
  loaded: boolean
}

const pageState = reactive<Record<TabKey, TabState>>({
  exhibitions: { page: 1, total: 0, hasMore: true, loaded: false },
  products: { page: 1, total: 0, hasMore: true, loaded: false },
  procurements: { page: 1, total: 0, hasMore: true, loaded: false },
})

const tabLabel = computed(() => tabs.find((t) => t.key === activeTab.value)?.label || '')
const currentList = computed<unknown[]>(() => {
  if (activeTab.value === 'exhibitions') return exhibitions.value
  if (activeTab.value === 'products') return products.value
  return procurements.value
})
const emptyMessage = computed(() => {
  const kw = searchKeyword.value.trim()
  return kw ? `未找到与"${kw}"相关的${tabLabel.value}` : '暂无数据'
})

onLoad((options) => {
  // 优先取 URL 上的 q 参数，其次从 storage 读（switchTab 跨 tab 传词用）
  let q = (options?.q as string) || ''
  if (!q) {
    q = (uni.getStorageSync('search_keyword') as string) || ''
  }
  if (q) {
    searchKeyword.value = q
    doSearch()
  }
})

function handleSearch(value: string) {
  searchKeyword.value = value.trim()
  if (!searchKeyword.value) {
    resetAll()
    searched.value = false
    return
  }
  doSearch()
}

function resetAll() {
  exhibitions.value = []
  products.value = []
  procurements.value = []
  pageState.exhibitions = { page: 1, total: 0, hasMore: true, loaded: false }
  pageState.products = { page: 1, total: 0, hasMore: true, loaded: false }
  pageState.procurements = { page: 1, total: 0, hasMore: true, loaded: false }
}

function switchTab(tab: TabKey) {
  if (activeTab.value === tab) return
  activeTab.value = tab
  // 当前关键词下该分类还没搜索过时自动补一次搜索
  if (searchKeyword.value && !pageState[tab].loaded) {
    doSearch()
  }
}

async function doSearch() {
  const q = searchKeyword.value.trim()
  if (!q) return
  searched.value = true
  loading.value = true
  const tab = activeTab.value
  try {
    const params = { search: q, page: 1, page_size: PAGE_SIZE }
    if (tab === 'exhibitions') {
      const res = await exhibitionApi.getList(params)
      exhibitions.value = toItems(res)
      updatePageState(tab, res, exhibitions.value)
    } else if (tab === 'products') {
      const res = await productApi.getList(params)
      products.value = toItems(res)
      updatePageState(tab, res, products.value)
    } else {
      const res = await procurementApi.getList(params)
      procurements.value = toItems(res)
      updatePageState(tab, res, procurements.value)
    }
  } catch (err) {
    console.error('Search error:', err)
    uni.showToast({ title: (err as Error)?.message || '搜索失败', icon: 'none' })
    pageState[tab].loaded = true
  } finally {
    loading.value = false
  }
}

function toItems<T>(res: PageResult<T>): T[] {
  return (res.list as T[] | undefined) || res.items || res.results || []
}

function updatePageState(tab: TabKey, res: { total?: number }, list: unknown[]) {
  const st = pageState[tab]
  st.page = 1
  st.total = res.total || list.length
  st.hasMore = list.length > 0 && list.length < st.total
  st.loaded = true
}

async function loadMore() {
  const q = searchKeyword.value.trim()
  const tab = activeTab.value
  const st = pageState[tab]
  if (!q || loading.value || loadingMore.value || !st.hasMore || !st.loaded) return
  loadingMore.value = true
  const nextPage = st.page + 1
  try {
    const params = { search: q, page: nextPage, page_size: PAGE_SIZE }
    if (tab === 'exhibitions') {
      const res = await exhibitionApi.getList(params)
      const items = toItems(res)
      exhibitions.value = exhibitions.value.concat(items)
      st.page = nextPage
      st.total = res.total || exhibitions.value.length
      st.hasMore = items.length > 0 && exhibitions.value.length < st.total
    } else if (tab === 'products') {
      const res = await productApi.getList(params)
      const items = toItems(res)
      products.value = products.value.concat(items)
      st.page = nextPage
      st.total = res.total || products.value.length
      st.hasMore = items.length > 0 && products.value.length < st.total
    } else {
      const res = await procurementApi.getList(params)
      const items = toItems(res)
      procurements.value = procurements.value.concat(items)
      st.page = nextPage
      st.total = res.total || procurements.value.length
      st.hasMore = items.length > 0 && procurements.value.length < st.total
    }
  } catch (err) {
    console.error('Load more error:', err)
    uni.showToast({ title: (err as Error)?.message || '加载失败', icon: 'none' })
  } finally {
    loadingMore.value = false
  }
}

onReachBottom(loadMore)

function goToExhibition(id: number) {
  uni.navigateTo({ url: `/pages/exhibitions/detail?id=${id}` })
}
function goToProduct(id: number) {
  uni.navigateTo({ url: `/pages/products/detail?id=${id}` })
}
function goToProcurement(id: number) {
  uni.navigateTo({ url: `/pages/procurements/detail?id=${id}` })
}
</script>

<template>
  <view class="page-wrapper">
    <!-- 顶部搜索框 -->
    <view class="search-header">
      <SearchBar v-model="searchKeyword" @search="handleSearch" />
    </view>

    <!-- 分类 tab：展会 / 产品 / 采购 -->
    <view class="search-tabs">
      <view
        v-for="tab in tabs"
        :key="tab.key"
        class="search-tab"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <text>{{ tab.label }}</text>
      </view>
    </view>

    <!-- 尚未搜索 -->
    <view v-if="!searched" class="search-hint text-center text-secondary">
      <text class="hint-icon">🔍</text>
      <text class="hint-text">输入关键词搜索展会、产品或采购需求</text>
    </view>

    <!-- 加载中 -->
    <LoadingSkeleton v-else-if="loading" :lines="6" />

    <!-- 空结果 -->
    <EmptyState v-else-if="currentList.length === 0" :message="emptyMessage" icon="🔍" />

    <!-- 展会结果 -->
    <view v-else-if="activeTab === 'exhibitions'" class="result-list">
      <ExpoCard
        v-for="e in exhibitions"
        :key="e.id"
        :exhibition="e"
        @click="goToExhibition(e.id)"
      />
    </view>

    <!-- 产品结果 -->
    <view v-else-if="activeTab === 'products'" class="result-list product-grid">
      <ProductCard
        v-for="p in products"
        :key="p.id"
        :product="p"
        @click="goToProduct(p.id)"
      />
    </view>

    <!-- 采购结果 -->
    <view v-else class="result-list">
      <ProcurementCard
        v-for="p in procurements"
        :key="p.id"
        :procurement="p"
        @click="goToProcurement(p.id)"
      />
    </view>

    <!-- 加载更多 / 到底提示 -->
    <view v-if="loadingMore" class="load-more text-center text-secondary">
      <text>加载中...</text>
    </view>
    <view
      v-else-if="searched && currentList.length > 0 && !pageState[activeTab].hasMore"
      class="load-more text-center text-secondary"
    >
      <text>没有更多了</text>
    </view>
  </view>
</template>

<style scoped>
.search-header {
  margin-bottom: 16px;
}

.search-tabs {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--color-border);
}

.search-tab {
  padding: 8px 4px;
  font-size: 15px;
  color: var(--color-text-secondary);
  position: relative;
}

.search-tab.active {
  color: var(--color-primary);
  font-weight: 600;
}

.search-tab.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 3px;
  border-radius: 2px;
  background: var(--color-primary);
}

.search-hint {
  padding: 80px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.hint-icon {
  font-size: 48px;
  opacity: 0.5;
}

.hint-text {
  font-size: 15px;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.product-grid {
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: space-between;
}

.product-grid :deep(.product-card) {
  width: 48%;
  margin-bottom: 16px;
}

.load-more {
  padding: 20px 0 8px;
  font-size: 13px;
}
</style>
