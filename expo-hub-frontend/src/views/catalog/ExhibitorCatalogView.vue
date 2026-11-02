<script setup lang="ts">
/**
 * 展商名录（公开只读）—— 对齐参考站 e.chtf.com/#/exhibitor 的信息架构
 *
 * 页面结构（参考站 → 本页）：
 *   搜索框              → SearchBar（live=false：回车/按钮才查）
 *   分类下拉            → 行业 / 城市 / 展会 三个 facets 下拉（带真实条数）
 *   横向展商卡（logo + 名称 + 展区/地址/展位号/浏览量 + 查看详情）
 *                      → 横向信息卡（CompanyAvatar + 名称 + 行业/城市/展位号 + 展品数 + 查看详情）
 *   分页（每页 10）     → PaginationBar（默认 20/页，可切 20/40/60）
 *
 * 数据全部来自 /catalog/exhibitors（后端 catalog 只读接口），页面不自造数字：
 * total / facets 直接回显接口值，取不到就显示空态或失败重试。
 *
 * 支持 `?exhibition_id=` 深链（展会详情页「参展展商 → 查看全部」跳进来）：
 * 后端按**参展关系表** `exhibition_exhibitors` 过滤，与展会详情页的展商数同口径。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SearchBar from '@/components/SearchBar.vue'
import CompanyAvatar from '@/components/CompanyAvatar.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { catalogApi, type CatalogExhibitor, type CatalogFacets, type CatalogQuery, type FacetItem, type PagedList } from '@/api/catalog'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'

/** 默认每页条数（参考站 10 条/页；名录体量大，默认 20 并允许切换） */
const DEFAULT_PAGE_SIZE = 20
const PAGE_SIZE_OPTIONS = [20, 40, 60]
const SKELETON_COUNT = 6

const route = useRoute()
const router = useRouter()

const keyword = ref('')
const industry = ref('')
const city = ref('')
const expo = ref('')

const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const total = ref(0)
const list = ref<CatalogExhibitor[]>([])
const facets = ref<CatalogFacets>({})

const loading = ref(true)
const failed = ref(false)

/** facets 未必每次回传：选项做并集累积，已选值不会因为翻页而消失 */
const industryOptions = ref<FacetItem[]>([])
const cityOptions = ref<FacetItem[]>([])
const expoOptions = ref<FacetItem[]>([])

/** SearchBar 只在初始化时读一次 modelValue，清空筛选时靠 :key 重建 */
const searchKey = ref(0)

/** 展会维度深链（来自 `?exhibition_id=`）；0 = 不按展会筛 */
const exhibitionId = ref(0)
/** 该展会的标题（只用于顶部作用域提示；取不到就不显示名字） */
const exhibitionTitle = ref('')

let requestSeq = 0

const totalPages = computed(() =>
  total.value > 0 ? Math.max(1, Math.ceil(total.value / pageSize.value)) : 1,
)

const hasFilter = computed(() =>
  Boolean(keyword.value.trim() || industry.value || city.value || expo.value || exhibitionId.value),
)

/** 副标题：数字只来自接口的 total / facets */
const subtitle = computed(() => {
  if (loading.value) return '正在读取名录数据…'
  if (failed.value) return '名录数据暂时没有取到，可点击重试。'
  const parts = [
    hasFilter.value
      ? `筛选到 ${formatCount(total.value)} 家展商`
      : `收录 ${formatCount(total.value)} 家展商`,
  ]
  const industryCount = facets.value.industries?.length ?? 0
  const cityCount = facets.value.cities?.length ?? 0
  if (industryCount > 0) parts.push(`${industryCount} 个行业`)
  if (cityCount > 0) parts.push(`${cityCount} 个城市`)
  return parts.join(' · ')
})

/** 顶部作用域条：正在按某个展会看名录（展会名取不到时只显示 id） */
const scopeText = computed(() => {
  if (!exhibitionId.value) return ''
  const name = exhibitionTitle.value || `展会 #${exhibitionId.value}`
  const count = loading.value ? '' : ` · ${formatCount(total.value)} 家参展展商`
  return `正在查看「${name}」的名录展商${count}`
})

/** ≥10000 显示「1.3 万」，其余千分位；缺失返回「—」 */
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

/**
 * 区分「接口失败」与「确实没有匹配」：catalogApi 失败时返回 EMPTY_PAGE
 * （list=[]、total=0、page=1、page_size=20，且没有 facets 键），
 * 成功响应按冻结契约必带 facets。与 ProductCatalogView 同一套判定。
 */
function looksLikeClientFallback(res: PagedList<CatalogExhibitor>): boolean {
  return (
    res.total === 0 &&
    res.list.length === 0 &&
    res.facets === undefined &&
    res.page_size === DEFAULT_PAGE_SIZE
  )
}

async function load(): Promise<void> {
  const seq = ++requestSeq
  loading.value = true
  failed.value = false

  const params: CatalogQuery = { page: page.value, page_size: pageSize.value }
  const kw = keyword.value.trim()
  if (kw) params.search = kw
  if (industry.value) params.industry = industry.value
  if (city.value) params.city = city.value
  if (expo.value) params.expo = expo.value
  if (exhibitionId.value) params.exhibition_id = exhibitionId.value

  try {
    const res = await catalogApi.getExhibitors(params)
    if (seq !== requestSeq) return
    if (looksLikeClientFallback(res)) {
      list.value = []
      total.value = 0
      failed.value = true
      return
    }
    list.value = Array.isArray(res.list) ? res.list : []
    total.value = Number.isFinite(Number(res.total)) ? Number(res.total) : 0
    facets.value = res.facets || {}
    industryOptions.value = mergeFacet(industryOptions.value, res.facets?.industries)
    cityOptions.value = mergeFacet(cityOptions.value, res.facets?.cities)
    expoOptions.value = mergeFacet(expoOptions.value, res.facets?.expos)
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

/** 只给顶部作用域条用：拿不到标题不影响列表本身 */
async function loadExhibitionTitle(): Promise<void> {
  if (!exhibitionId.value) {
    exhibitionTitle.value = ''
    return
  }
  try {
    const detail = (await exhibitionApi.getDetail(exhibitionId.value)) as Exhibition | null
    exhibitionTitle.value = (detail?.title || '').toString().trim()
  } catch {
    exhibitionTitle.value = ''
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

/** 清空全部筛选（含关键词与展会作用域），同步清掉 URL 上的 exhibition_id */
function resetAll(): void {
  keyword.value = ''
  industry.value = ''
  city.value = ''
  expo.value = ''
  searchKey.value += 1
  page.value = 1
  if (exhibitionId.value) {
    exhibitionId.value = 0
    exhibitionTitle.value = ''
    const query = { ...route.query }
    delete query.exhibition_id
    void router.replace({ query })
  }
  void load()
}

/** 从「某展会作用域」退回全量名录 */
function clearExhibitionScope(): void {
  resetAll()
}

/** 分页组件是纯展示的：页码/每页条数由父级驱动 */
function onPageChange(payload: { page: number; pageSize: number }): void {
  page.value = payload.page
  if (payload.pageSize && payload.pageSize !== pageSize.value) pageSize.value = payload.pageSize
  void load()
}

onMounted(() => {
  const queryExhibition = Number(route.query.exhibition_id)
  if (Number.isFinite(queryExhibition) && queryExhibition > 0) exhibitionId.value = queryExhibition
  const queryKeyword = (route.query.q ?? route.query.keywords ?? '').toString().trim()
  if (queryKeyword) keyword.value = queryKeyword

  void loadExhibitionTitle()
  void load()
})
</script>

<template>
  <div class="page">
    <header class="page-head">
      <h1 class="page-title">展商名录</h1>
      <p class="page-sub">{{ subtitle }}</p>
    </header>

    <!-- 展会作用域：从展会详情页「参展展商 → 查看全部」跳进来时显示 -->
    <div v-if="exhibitionId" class="scope-bar">
      <span class="scope-text">{{ scopeText }}</span>
      <button type="button" class="scope-btn" @click="clearExhibitionScope">查看全部名录</button>
    </div>

    <div class="toolbar">
      <div class="search-wrap">
        <SearchBar
          :key="searchKey"
          v-model="keyword"
          :live="false"
          placeholder="搜索展商名称或关键词"
          @search="onSearch"
        />
      </div>
    </div>

    <div class="filters">
      <label class="filter">
        <span class="filter-label">行业</span>
        <select v-model="industry" class="filter-select" @change="applyFilter">
          <option value="">全部行业</option>
          <option v-for="opt in industryOptions" :key="opt.value" :value="opt.value">
            {{ opt.value }}（{{ formatCount(opt.count) }}）
          </option>
        </select>
      </label>

      <label class="filter">
        <span class="filter-label">城市</span>
        <select v-model="city" class="filter-select" @change="applyFilter">
          <option value="">全部城市</option>
          <option v-for="opt in cityOptions" :key="opt.value" :value="opt.value">
            {{ opt.value }}（{{ formatCount(opt.count) }}）
          </option>
        </select>
      </label>

      <label class="filter">
        <span class="filter-label">名录展会</span>
        <select v-model="expo" class="filter-select" @change="applyFilter">
          <option value="">全部展会</option>
          <option v-for="opt in expoOptions" :key="opt.value" :value="opt.value">
            {{ opt.value }}（{{ formatCount(opt.count) }}）
          </option>
        </select>
      </label>

      <button v-if="hasFilter" type="button" class="reset-btn" @mousedown.prevent @click="resetAll">
        清空筛选
      </button>
    </div>

    <!-- 加载中：列表骨架 -->
    <div v-if="loading" class="list" aria-busy="true" aria-label="加载中">
      <div v-for="n in SKELETON_COUNT" :key="n" class="sk-row"></div>
    </div>

    <!-- 失败 -->
    <div v-else-if="failed" class="state">
      <p class="state-title">加载失败，点击重试</p>
      <p class="state-text">名录接口这次没有返回数据；如果刚调整过筛选，也可以清空条件再看一次。</p>
      <div class="state-actions">
        <button type="button" class="primary-btn" @click="load">重试</button>
        <button type="button" class="ghost-btn" @mousedown.prevent @click="resetAll">清空筛选</button>
      </div>
    </div>

    <!-- 空态 -->
    <div v-else-if="list.length === 0" class="state">
      <p class="state-title">没有匹配的展商</p>
      <p class="state-text">换个关键词，或清空筛选条件再看一次。</p>
      <div class="state-actions">
        <button type="button" class="primary-btn" @mousedown.prevent @click="resetAll">清空筛选</button>
      </div>
    </div>

    <!-- 列表：整行可点进详情 -->
    <div v-else class="list">
      <router-link
        v-for="item in list"
        :key="item.id"
        class="exh-row"
        :to="{ name: 'catalog-exhibitor-detail', params: { id: item.id } }"
      >
        <CompanyAvatar :name="item.name" :size="56" class="exh-avatar" />

        <div class="exh-main">
          <h2 class="exh-name" :title="item.name">{{ item.name }}</h2>
          <p v-if="item.name_en" class="exh-name-en" :title="item.name_en">{{ item.name_en }}</p>
          <div class="exh-tags">
            <span v-if="item.industry" class="tag">🏷️ {{ item.industry }}</span>
            <span v-if="item.city" class="tag">📍 {{ item.city }}</span>
            <span v-if="item.booth_no" class="tag">🔖 展位 {{ item.booth_no }}</span>
            <span v-if="item.product_count" class="tag tag-soft">📦 {{ item.product_count }} 件展品</span>
          </div>
        </div>

        <div class="exh-side">
          <p class="exh-expo" :title="item.expo_name || ''">
            {{ item.expo_name || '名录展会未标注' }}
          </p>
          <span class="exh-go">查看详情 ›</span>
        </div>
      </router-link>
    </div>

    <PaginationBar
      v-if="!loading && !failed && total > 0"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      :loading="loading"
      :page-size-options="PAGE_SIZE_OPTIONS"
      storage-key="catalog-exhibitors-page-size"
      unit="家展商"
      @change="onPageChange"
    />
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

/* 展会作用域条（深链进来时） */
.scope-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  border-radius: var(--radius-btn);
}
.scope-text {
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: var(--brand-700);
  font-weight: 600;
}
.scope-btn {
  padding: 6px var(--space-3);
  border: 1px solid var(--brand-300);
  border-radius: var(--radius-sm);
  background: var(--surface-0);
  color: var(--brand-600);
  font-size: var(--font-xs);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
}
.scope-btn:hover {
  border-color: var(--brand-500);
  background: var(--surface-0);
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

/* 列表：一行一家展商（参考站的横向卡片，换成本站设计令牌） */
.list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.exh-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  color: inherit;
  text-decoration: none;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.exh-row:hover {
  transform: translateY(-2px);
  border-color: var(--brand-300);
  box-shadow: var(--shadow-hover);
  color: inherit;
}
.exh-row:focus-visible {
  outline: 2px solid var(--brand-500);
  outline-offset: 2px;
}

.exh-avatar {
  flex: none;
}

.exh-main {
  flex: 1 1 auto;
  min-width: 0;
}
.exh-name {
  font-size: var(--font-body);
  line-height: 1.4;
  font-weight: 600;
  color: var(--ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.exh-name-en {
  margin-top: 2px;
  font-size: var(--font-xs);
  line-height: var(--line-xs);
  color: var(--ink-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.exh-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-top: var(--space-2);
}
.tag {
  padding: 2px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: var(--font-xs);
  line-height: 1.6;
  white-space: nowrap;
}
.tag-soft {
  background: var(--surface-2);
  color: var(--ink-700);
}

.exh-side {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-2);
  max-width: 40%;
  text-align: right;
}
.exh-expo {
  font-size: var(--font-xs);
  line-height: var(--line-xs);
  color: var(--ink-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 18rem;
}
.exh-go {
  font-size: var(--font-xs);
  color: var(--brand-600);
  white-space: nowrap;
}

/* 骨架 */
.sk-row {
  height: 96px;
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
  .sk-row {
    animation: none;
  }
  .exh-row {
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
  .exh-row {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: var(--space-3);
  }
  .exh-side {
    flex: 1 1 100%;
    max-width: 100%;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    text-align: left;
  }
  .exh-expo {
    max-width: 70%;
  }
}
</style>
