<script setup lang="ts">
/**
 * 展品库（公开只读）
 *
 * 数据全部来自 @/api/catalog（后端 /catalog/products），页面不自造任何数字：
 * 取不到就显示「—」或空态。
 *
 * 状态流转：关键词回车 / 分类·展会下拉变化 / 翻页 → 组装 query → load()
 * 每次请求带自增序号，只采纳当前这次请求的响应。
 */
import { computed, onMounted, ref } from 'vue'
import SearchBar from '@/components/SearchBar.vue'
import { categoryImage } from '@/utils/categoryImage'
import {
  catalogApi,
  type CatalogFacets,
  type CatalogProduct,
  type CatalogQuery,
  type FacetItem,
  type PagedList,
} from '@/api/catalog'

/** 每页 24 条（桌面 4 列 × 6 行）：分页交给后端，前端不一次性渲染全量数据 */
const PAGE_SIZE = 24
/** 骨架块数量 */
const SKELETON_COUNT = 8

/**
 * api/catalog.ts 里的 CatalogQuery 只声明了 industry/city（展商维度），
 * 而 /catalog/products 的冻结契约里筛选键是 category。api 客户端不让改，
 * 这里在页面内做一次类型扩展（运行时 params 原样进 axios query，行为一致）。
 */
type ProductQuery = CatalogQuery & { category?: string }

const keyword = ref('')
const category = ref('')
const expo = ref('')

const page = ref(1)
const total = ref(0)
const list = ref<CatalogProduct[]>([])
const facets = ref<CatalogFacets>({})

const loading = ref(true)
const failed = ref(false)

/** facets 未必每次回传，选项做并集累积，已选值不会消失 */
const categoryOptions = ref<FacetItem[]>([])
const expoOptions = ref<FacetItem[]>([])

/** SearchBar 只在初始化时读一次 modelValue，清空筛选时靠 :key 重建 */
const searchKey = ref(0)

/** 图片加载失败的商品：不回填假图，改走「品类占位图」，避免破图 */
const brokenImageIds = ref<number[]>([])
/** 品类占位图是否加载失败（本地静态图；失败则整页退回渐变 + 首字） */
const coverBroken = ref(false)

let requestSeq = 0

const totalPages = computed(() =>
  total.value > 0 ? Math.max(1, Math.ceil(total.value / PAGE_SIZE)) : 1,
)

const hasFilter = computed(() =>
  Boolean(keyword.value.trim() || category.value || expo.value),
)

/** 副标题：数字只来自接口的 total / facets */
const subtitle = computed(() => {
  if (loading.value) return '正在读取展品数据…'
  if (failed.value) return '目录数据暂时没有取到，可点击重试。'
  const expoCount = facets.value.expos?.length ?? 0
  const categoryCount = facets.value.categories?.length ?? 0
  const parts = [
    hasFilter.value
      ? `筛选到 ${formatCount(total.value)} 件展品`
      : `收录 ${formatCount(total.value)} 件展品`,
  ]
  if (expoCount > 0) parts.push(`覆盖 ${expoCount} 场展会`)
  if (categoryCount > 0) parts.push(`${categoryCount} 个分类`)
  return parts.join(' · ')
})

/** ≥10000 显示「3.2 万」，其余按千分位；缺失返回「—」 */
function formatCount(value?: number | null): string {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return '—'
  if (n >= 10000) {
    const wan = n / 10000
    const rounded = wan >= 100 ? Math.round(wan) : Math.round(wan * 10) / 10
    return `${rounded} 万`
  }
  return n.toLocaleString('zh-CN')
}

function orDash(value?: string | null): string {
  const text = (value ?? '').toString().trim()
  return text || '—'
}

/** 无图时展示的名称首字（水印），空名称也不会渲染出空方块 */
function firstChar(name?: string | null): string {
  const text = (name ?? '').trim()
  return text ? Array.from(text)[0] : '展'
}

/** 合并 facet 选项：同值取较大 count，保持首次出现顺序 */
function mergeFacet(prev: FacetItem[], next?: FacetItem[] | null): FacetItem[] {
  if (!Array.isArray(next) || next.length === 0) return prev
  const merged = new Map<string, FacetItem>()
  for (const item of prev) merged.set(item.value, item)
  for (const item of next) {
    const value = typeof item?.value === 'string' ? item.value.trim() : ''
    if (!value) continue
    const count = Number.isFinite(Number(item.count)) ? Number(item.count) : 0
    const old = merged.get(value)
    merged.set(value, { value, count: Math.max(old?.count ?? 0, count) })
  }
  return Array.from(merged.values())
}

function markBroken(id: number): void {
  if (!brokenImageIds.value.includes(id)) brokenImageIds.value.push(id)
}

/**
 * 区分「接口失败」与「确实没有匹配」。catalogApi 失败时一律返回空结构
 * （EMPTY_PAGE：list=[]、total=0、page=1、page_size=20，且没有 facets 键），
 * 而成功响应按冻结契约必带 facets，page_size 回显请求值（本页固定请求 24）。
 * 因此「total=0 + 无 facets + page_size=20」判为请求失败。
 * 后端若调整 EMPTY_PAGE 默认值，这里会退化成「当成空态」（更安全的一侧）。
 */
function looksLikeClientFallback(res: PagedList<CatalogProduct>): boolean {
  return (
    res.total === 0 &&
    res.list.length === 0 &&
    res.facets === undefined &&
    res.page_size === 20
  )
}

function hasUsableImage(item: CatalogProduct): boolean {
  return Boolean(item.image) && !brokenImageIds.value.includes(item.id)
}

async function load(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  failed.value = false

  const params: ProductQuery = { page: page.value, page_size: PAGE_SIZE }
  const kw = keyword.value.trim()
  if (kw) params.search = kw
  if (category.value) params.category = category.value
  if (expo.value) params.expo = expo.value

  try {
    const res = await catalogApi.getProducts(params)
    if (seq !== requestSeq) return
    if (looksLikeClientFallback(res)) {
      // 拿到了客户端兜底结构：按「请求失败」处理，不冒充「没有匹配」
      list.value = []
      total.value = 0
      failed.value = true
      return
    }
    list.value = Array.isArray(res.list) ? res.list : []
    total.value = Number.isFinite(Number(res.total)) ? Number(res.total) : 0
    facets.value = res.facets || {}
    categoryOptions.value = mergeFacet(categoryOptions.value, res.facets?.categories)
    expoOptions.value = mergeFacet(expoOptions.value, res.facets?.expos)
    // 页码以服务端为准；空结果保持请求页码，不来回跳
    const serverPage = Number(res.page)
    if (total.value > 0 && Number.isFinite(serverPage) && serverPage > 0) page.value = serverPage
  } catch {
    if (seq !== requestSeq) return
    list.value = []
    total.value = 0
    failed.value = true
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

/** 回车 / 搜索按钮 / 失焦确认：关键词变了就回到第 1 页 */
function onSearch(value: string): void {
  keyword.value = value
  page.value = 1
  void load()
}

/** 下拉选中后立即查询，并回到第 1 页 */
function applyFilter(): void {
  page.value = 1
  void load()
}

/** 清空全部筛选（含关键词），重建 SearchBar 同步清空输入框 */
function resetAll(): void {
  keyword.value = ''
  category.value = ''
  expo.value = ''
  searchKey.value += 1
  page.value = 1
  void load()
}

function goPage(next: number): void {
  if (next < 1 || next > totalPages.value || next === page.value) return
  page.value = next
  void load()
  if (typeof window !== 'undefined') {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page">
    <header class="page-head">
      <h1 class="page-title">展品库</h1>
      <p class="page-sub">{{ subtitle }}</p>
    </header>

    <div class="toolbar">
      <div class="search-wrap">
        <!-- live=false：输入过程不发请求，回车 / 点「搜索」才查 -->
        <SearchBar
          :key="searchKey"
          v-model="keyword"
          :live="false"
          placeholder="搜索展品名称或关键词"
          @search="onSearch"
        />
      </div>
    </div>

    <div class="filters">
      <label class="filter">
        <span class="filter-label">分类</span>
        <select v-model="category" class="filter-select" @change="applyFilter">
          <option value="">全部分类</option>
          <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">
            {{ opt.value }}（{{ formatCount(opt.count) }}）
          </option>
        </select>
      </label>

      <label class="filter">
        <span class="filter-label">展会</span>
        <select v-model="expo" class="filter-select" @change="applyFilter">
          <option value="">全部展会</option>
          <option v-for="opt in expoOptions" :key="opt.value" :value="opt.value">
            {{ opt.value }}（{{ formatCount(opt.count) }}）
          </option>
        </select>
      </label>

      <button
        v-if="hasFilter"
        type="button"
        class="reset-btn"
        @mousedown.prevent
        @click="resetAll"
      >
        清空筛选
      </button>
    </div>

    <!-- 加载中：骨架占位 -->
    <div v-if="loading" class="grid" aria-busy="true" aria-label="加载中">
      <div v-for="n in SKELETON_COUNT" :key="n" class="sk-card"></div>
    </div>

    <!-- 失败 -->
    <div v-else-if="failed" class="state">
      <p class="state-title">加载失败，点击重试</p>
      <p class="state-text">展品接口这次没有返回数据；如果刚调整过筛选，也可以清空条件再看一次。</p>
      <div class="state-actions">
        <button type="button" class="primary-btn" @click="load">重试</button>
        <button type="button" class="ghost-btn" @mousedown.prevent @click="resetAll">
          清空筛选
        </button>
      </div>
    </div>

    <!-- 空态 -->
    <div v-else-if="list.length === 0" class="state">
      <p class="state-title">没有匹配的展品</p>
      <p class="state-text">换个关键词，或清空筛选条件再看一次。</p>
      <div class="state-actions">
        <button type="button" class="primary-btn" @mousedown.prevent @click="resetAll">
          清空筛选
        </button>
      </div>
    </div>

    <!-- 列表：整块卡片可点进详情 -->
    <div v-else class="grid">
      <router-link
        v-for="item in list"
        :key="item.id"
        class="pd-card"
        :to="{ name: 'catalog-product-detail', params: { id: item.id } }"
      >
        <div class="pd-thumb">
          <img
            v-if="hasUsableImage(item)"
            :src="item.image as string"
            :alt="item.name"
            loading="lazy"
            class="pd-thumb-img"
            @error="markBroken(item.id)"
          />
          <!-- 无图 / 加载失败：该品类的几何占位图；占位图也失败才退回首字水印，不出现破图 -->
          <div v-else class="pd-thumb-fallback">
            <img
              v-if="!coverBroken"
              class="pd-thumb-cover"
              :src="categoryImage(item.category)"
              alt=""
              aria-hidden="true"
              loading="lazy"
              decoding="async"
              @error="coverBroken = true"
            />
            <span v-else class="pd-thumb-watermark" aria-hidden="true">{{ firstChar(item.name) }}</span>
          </div>
        </div>

        <h2 class="pd-name">{{ item.name }}</h2>
        <p v-if="item.category" class="pd-cat">{{ item.category }}</p>
        <p class="pd-exhibitor">{{ orDash(item.exhibitor_name) }}</p>
        <p class="pd-expo">{{ orDash(item.expo_name) }}</p>
      </router-link>
    </div>

    <!-- 分页：上一页 / 下一页 + 第 X / Y 页 · 共 N 条 -->
    <nav v-if="!loading && !failed && total > 0" class="pager" aria-label="分页">
      <button type="button" class="pager-btn" :disabled="page <= 1" @click="goPage(page - 1)">
        上一页
      </button>
      <span class="pager-info">
        第 {{ page }} / {{ totalPages }} 页 · 共 {{ formatCount(total) }}条
      </span>
      <button
        type="button"
        class="pager-btn"
        :disabled="page >= totalPages"
        @click="goPage(page + 1)"
      >
        下一页
      </button>
    </nav>
  </div>
</template>

<style scoped>
.page {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-6) var(--space-5) var(--space-8);
}

.page-head {
  margin-bottom: var(--space-4);
}
.page-title {
  font-size: var(--font-h1);
  line-height: var(--line-h1);
  font-weight: var(--weight-h1);
  color: var(--ink-900);
  letter-spacing: -0.02em;
}
.page-sub {
  margin-top: var(--space-2);
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: var(--ink-500);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: center;
  margin-bottom: var(--space-3);
}
.search-wrap {
  flex: 1 1 320px;
  min-width: 220px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
}
.filter {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-1) 0 var(--space-3);
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-btn);
  transition: border-color 0.15s ease;
}
.filter:focus-within {
  border-color: var(--brand-500);
}
.filter-label {
  font-size: var(--font-xs);
  color: var(--ink-500);
  white-space: nowrap;
}
.filter-select {
  max-width: 15rem;
  padding: 9px var(--space-2);
  border: none;
  outline: none;
  background: transparent;
  color: var(--ink-700);
  font-size: var(--font-sm);
  font-family: inherit;
  cursor: pointer;
}

.reset-btn {
  padding: 9px var(--space-4);
  border: 1px solid var(--brand-300);
  border-radius: var(--radius-btn);
  background: var(--surface-0);
  color: var(--brand-600);
  font-size: var(--font-sm);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
}
.reset-btn:hover {
  border-color: var(--brand-500);
  background: var(--brand-50);
}

/* 桌面 4 列 / 平板 3 列 / 手机 2 列 */
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}
@media (min-width: 768px) {
  .grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (min-width: 1200px) {
  .grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.pd-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  color: inherit;
  text-decoration: none;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.pd-card:hover {
  transform: translateY(-2px);
  border-color: var(--brand-300);
  box-shadow: var(--shadow-hover);
  color: inherit;
}
.pd-card:focus-visible {
  outline: 2px solid var(--brand-500);
  outline-offset: 2px;
}

.pd-thumb {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: var(--radius-md);
  background: var(--surface-2);
}
.pd-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.pd-thumb-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--brand-800) 0%, var(--brand-600) 100%);
}
/* 品类占位图：与真实图同一图位、同一裁切，切换时不会跳版 */
.pd-thumb-cover {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.pd-thumb-watermark {
  font-size: var(--font-h2);
  font-weight: var(--weight-h2);
  color: var(--surface-0);
  opacity: 0.32;
  line-height: 1;
}

.pd-name {
  font-size: var(--font-sm);
  line-height: 1.45;
  font-weight: 600;
  color: var(--ink-900);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: calc(var(--font-sm) * 1.45 * 2);
}
.pd-cat {
  align-self: flex-start;
  padding: 2px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: var(--font-xs);
  line-height: 1.6;
}
.pd-exhibitor {
  margin-top: auto;
  font-size: var(--font-xs);
  line-height: var(--line-xs);
  color: var(--ink-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pd-expo {
  font-size: var(--font-xs);
  line-height: var(--line-xs);
  color: var(--ink-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 骨架 */
.sk-card {
  min-height: 232px;
  border-radius: var(--radius-card);
  background: linear-gradient(
    90deg,
    var(--surface-2) 25%,
    var(--surface-1) 50%,
    var(--surface-2) 75%
  );
  background-size: 200% 100%;
  animation: sk-shimmer 1.3s ease-in-out infinite;
}
@keyframes sk-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .sk-card {
    animation: none;
  }
  .pd-card {
    transition: none;
  }
}

/* 失败 / 空态 */
.state {
  padding: var(--space-7) var(--space-4);
  text-align: center;
  background: var(--surface-1);
  border: 1px dashed var(--ink-100);
  border-radius: var(--radius-card);
}
.state-title {
  font-size: var(--font-h3);
  line-height: var(--line-h3);
  font-weight: var(--weight-h3);
  color: var(--ink-900);
}
.state-text {
  margin-top: var(--space-2);
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: var(--ink-500);
}
.state-actions {
  margin-top: var(--space-4);
  display: flex;
  justify-content: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.primary-btn {
  padding: 10px var(--space-5);
  border: none;
  border-radius: var(--radius-btn);
  background: var(--brand-700);
  color: var(--surface-0);
  font-size: var(--font-sm);
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease;
}
.primary-btn:hover {
  background: var(--brand-600);
}

.ghost-btn {
  padding: 10px var(--space-5);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-btn);
  background: var(--surface-0);
  color: var(--ink-700);
  font-size: var(--font-sm);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
}
.ghost-btn:hover {
  border-color: var(--brand-500);
  color: var(--brand-600);
}

/* 分页 */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--ink-100);
}
.pager-btn {
  padding: 9px var(--space-4);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-btn);
  background: var(--surface-0);
  color: var(--ink-700);
  font-size: var(--font-sm);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
}
.pager-btn:hover:not(:disabled) {
  border-color: var(--brand-500);
  color: var(--brand-600);
  background: var(--brand-50);
}
.pager-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.pager-info {
  font-size: var(--font-sm);
  color: var(--ink-500);
}

@media (max-width: 640px) {
  .page {
    padding: var(--space-5) var(--space-4) var(--space-7);
  }
  .page-title {
    font-size: var(--font-h2);
    line-height: var(--line-h2);
  }
  .filter-select {
    max-width: 9rem;
  }
  .grid {
    gap: var(--space-3);
  }
  .pd-card {
    padding: var(--space-2);
  }
}
</style>
