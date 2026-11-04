<script setup lang="ts">
/**
 * 展会评估 · 列表页
 *
 * 这个页面回答一个问题：**这个展值不值得去。**
 * 它不回答"有哪些展"——那是 /exhibitions 的事。
 * 所以页面上要出现的是判断依据（客源可得性、时间窗口、数据来源），
 * 而不是展会宣传文案。
 *
 * 三条贯穿全页的克制：
 * 1) `unknown` 不做视觉降级处理，也不染成警告色。缺数据不是坏消息。
 * 2) 每个数字都带来源与口径。去展网的观众数偏低 20~25%，不标出来等于让用户
 *    拿一个系统性偏差当事实。
 * 3) 分位是**相对档位**，页头必须写明样本量，否则"摊薄"会被读成绝对判断。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BandBadge from '@/components/persona/BandBadge.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import {
  e1Tone,
  e4Tone,
  fmtCount,
  fmtDateRange,
  fmtRatio,
  personaApi,
  type E1Band,
  type E4Band,
  type ExpoPersonaItem,
  type PersonaListParams,
  type PersonaOverview,
} from '@/api/persona'

const route = useRoute()
const router = useRouter()

const items = ref<ExpoPersonaItem[]>([])
const overview = ref<PersonaOverview | null>(null)
const loading = ref(true)
const failed = ref(false)

const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = ref(1)

const q = ref('')
const category = ref('')
const ratioBand = ref<'' | E1Band>('')
const e4Band = ref<'' | E4Band>('')
const upcoming = ref(false)
const sort = ref<'start_date' | 'ratio' | 'name'>('start_date')
const order = ref<'asc' | 'desc'>('asc')

/** 一次性把 URL query 读进来：页面可分享、可后退、刷新不丢筛选 */
function readQuery() {
  const s = (k: string): string => {
    const v = route.query[k]
    return typeof v === 'string' ? v : ''
  }
  q.value = s('q')
  category.value = s('category')
  ratioBand.value = (s('ratio_band') as E1Band) || ''
  e4Band.value = (s('e4_band') as E4Band) || ''
  upcoming.value = s('upcoming') === 'true'
  sort.value = (s('sort') as typeof sort.value) || 'start_date'
  order.value = (s('order') as typeof order.value) || 'asc'
  page.value = Number(s('page')) || 1
  pageSize.value = Number(s('page_size')) || 20
}
readQuery()

/** 筛选变化 → 写回 URL（replace，不在历史里堆一串筛选状态） */
function syncQuery() {
  const query: Record<string, string> = {}
  if (q.value) query.q = q.value
  if (category.value) query.category = category.value
  if (ratioBand.value) query.ratio_band = ratioBand.value
  if (e4Band.value) query.e4_band = e4Band.value
  if (upcoming.value) query.upcoming = 'true'
  if (sort.value !== 'start_date') query.sort = sort.value
  if (order.value !== 'asc') query.order = order.value
  if (page.value > 1) query.page = String(page.value)
  if (pageSize.value !== 20) query.page_size = String(pageSize.value)
  router.replace({ query })
}

async function fetchList() {
  loading.value = true
  failed.value = false
  try {
    const params: PersonaListParams = {
      page: page.value,
      page_size: pageSize.value,
      sort: sort.value,
      order: order.value,
    }
    if (q.value.trim()) params.q = q.value.trim()
    if (category.value) params.category = category.value
    if (ratioBand.value) params.ratio_band = ratioBand.value
    if (e4Band.value) params.e4_band = e4Band.value
    if (upcoming.value) params.upcoming = true

    const res = await personaApi.getExpos(params)
    items.value = res.items || []
    total.value = res.pagination?.total ?? 0
    totalPages.value = res.pagination?.pages ?? 1
  } catch {
    failed.value = true
    items.value = []
  } finally {
    loading.value = false
  }
}

async function fetchOverview() {
  try {
    overview.value = await personaApi.getOverview()
  } catch {
    // 总览失败不影响列表，静默降级
  }
}

onMounted(() => {
  fetchOverview()
  fetchList()
})

watch([page, pageSize], () => {
  syncQuery()
  fetchList()
})

function applyFilter() {
  page.value = 1
  syncQuery()
  fetchList()
}

function setRatioBand(b: '' | E1Band) {
  ratioBand.value = ratioBand.value === b ? '' : b
  applyFilter()
}

function resetAll() {
  q.value = ''
  category.value = ''
  ratioBand.value = ''
  e4Band.value = ''
  upcoming.value = false
  sort.value = 'start_date'
  order.value = 'asc'
  applyFilter()
}

function toggleSort(field: 'start_date' | 'ratio' | 'name') {
  if (sort.value === field) {
    order.value = order.value === 'asc' ? 'desc' : 'asc'
  } else {
    sort.value = field
    order.value = field === 'ratio' ? 'desc' : 'asc'
  }
  applyFilter()
}

function goDetail(slug: string) {
  router.push({ name: 'expo-intel-detail', params: { slug } })
}

/** 筛选激活了多少条——让用户随时知道自己在看子集，而不是全部 */
const activeFilters = computed(() => {
  let n = 0
  if (q.value.trim()) n++
  if (category.value) n++
  if (ratioBand.value) n++
  if (e4Band.value) n++
  if (upcoming.value) n++
  return n
})

const e1Chips = computed(() => {
  const d = overview.value?.e1_distribution || {}
  const order: E1Band[] = ['ample', 'normal', 'thin', 'severe', 'unknown']
  return order
    .filter((b) => d[b])
    .map((b) => ({ band: b, label: d[b].label, count: d[b].count }))
})

const e4Chips = computed(() => {
  const d = overview.value?.e4_distribution || {}
  const order: E4Band[] = ['ongoing', 'impossible', 'critical', 'urgent', 'normal', 'ample', 'closed', 'unknown']
  return order
    .filter((b) => d[b] && d[b].count > 0)
    .map((b) => ({ band: b, label: d[b].label, count: d[b].count }))
})

/** 数据缺口是必须暴露的，不能藏进设置里 */
const coverageNote = computed(() => {
  const c = overview.value?.coverage
  if (!c) return ''
  const pct = (k: string) => (c[k] ? Math.round(c[k].rate * 100) : 0)
  return `观众数 ${pct('visitor_count')}% · 展商数 ${pct('exhibitor_count')}% · 开展日 ${pct('start_date')}%`
})

const calibr = computed(() => overview.value?.calibration || null)
</script>

<template>
  <div class="container page-wrapper intel-page">
    <!-- 页头：先说清楚这个页面不是什么 -->
    <header class="intel-head">
      <div class="ih-main">
        <h1>展会评估</h1>
        <p class="ih-sub">
          判断一个展<strong>值不值得去</strong>：客源够不够、时间赶不赶、数据可不可信。
        </p>
      </div>
      <div v-if="calibr" class="ih-calib">
        <div class="ihc-line">
          <span class="ihc-k">档位基准</span>
          <span class="ihc-v">{{ calibr.version }} · n={{ calibr.n }}</span>
        </div>
        <p class="ihc-note">
          四档按<strong>本样本</strong>分位切分，是横向排名，不是绝对好坏。
        </p>
      </div>
    </header>

    <!-- 诚实声明条：这一行是整页的信用基础 -->
    <div class="honesty-bar">
      <span class="hb-icon" aria-hidden="true">ⓘ</span>
      <span class="hb-text">
        「无法判断」= 我们没拿到足够数据算比值，<strong>不代表这个展不好</strong>。
        当前覆盖：{{ coverageNote || '加载中' }}。
        标注「第三方源」的数字来自会展平台，观众数实测偏低 20~25%，只用于排序参考。
      </span>
    </div>

    <!-- 档位快筛：直接点分布筛，比下拉框快 -->
    <section v-if="e1Chips.length" class="chip-row">
      <span class="chip-row-label">客源可得性</span>
      <button
        v-for="c in e1Chips"
        :key="c.band"
        class="dist-chip"
        :class="[`tone-${e1Tone(c.band)}`, { active: ratioBand === c.band }]"
        @click="setRatioBand(c.band)"
      >
        {{ c.label }}<b>{{ c.count }}</b>
      </button>
      <span class="chip-row-label ml">时间窗口</span>
      <button
        v-for="c in e4Chips"
        :key="c.band"
        class="dist-chip"
        :class="[`tone-${e4Tone(c.band)}`, { active: e4Band === c.band }]"
        @click="((e4Band = e4Band === c.band ? '' : c.band), applyFilter())"
      >
        {{ c.label }}<b>{{ c.count }}</b>
      </button>
    </section>

    <!-- 筛选条 -->
    <section class="filter-bar">
      <input
        v-model="q"
        class="fi-search"
        type="search"
        placeholder="搜展名、城市或展馆"
        @keyup.enter="applyFilter"
      />
      <select v-model="category" class="fi-select" @change="applyFilter">
        <option value="">全部品类</option>
        <option v-for="c in overview?.categories || []" :key="c.category" :value="c.category">
          {{ c.category }}（{{ c.count }}）
        </option>
      </select>
      <label class="fi-check">
        <input v-model="upcoming" type="checkbox" @change="applyFilter" />
        <span>只看未闭幕</span>
      </label>
      <button class="btn btn-sm btn-primary" @click="applyFilter">筛选</button>
      <button v-if="activeFilters" class="btn btn-sm btn-outline" @click="resetAll">
        清空（{{ activeFilters }}）
      </button>
      <div class="fi-spacer"></div>
      <div class="sort-group">
        <button
          v-for="s in [
            { k: 'start_date', t: '开展日' },
            { k: 'ratio', t: '观众/展商比' },
            { k: 'name', t: '展名' },
          ]"
          :key="s.k"
          class="sort-btn"
          :class="{ active: sort === s.k }"
          @click="toggleSort(s.k as 'start_date' | 'ratio' | 'name')"
        >
          {{ s.t }}<span v-if="sort === s.k" class="sort-arrow">{{ order === 'asc' ? '↑' : '↓' }}</span>
        </button>
      </div>
    </section>

    <!-- 列表 -->
    <LoadingSkeleton v-if="loading" :lines="8" />

    <EmptyState
      v-else-if="failed"
      icon="⚠️"
      message="画像接口没有响应，请确认后端已启动"
    />

    <EmptyState
      v-else-if="items.length === 0"
      icon="🔍"
      message="没有符合条件的展会，试试放宽筛选"
    />

    <div v-else class="intel-list">
      <article
        v-for="it in items"
        :key="it.slug"
        class="intel-row"
        tabindex="0"
        role="link"
        @click="goDetail(it.slug)"
        @keyup.enter="goDetail(it.slug)"
      >
        <!-- 左：身份 -->
        <div class="ir-id">
          <div class="ir-title-line">
            <h3 class="ir-name">{{ it.name_cn }}</h3>
            <span v-if="it.primary_category" class="ir-cat">{{ it.primary_category }}</span>
            <span v-if="it.scale_source === 'qufair'" class="ir-src" :title="it.scale_source_label">
              第三方源
            </span>
          </div>
          <div class="ir-meta">
            <span>{{ it.city || '城市未知' }}</span>
            <span v-if="it.venue_name" class="ir-venue">· {{ it.venue_name }}</span>
            <span class="ir-date">· {{ fmtDateRange(it.start_date, it.end_date) }}</span>
          </div>
        </div>

        <!-- 中：原始数字 -->
        <div class="ir-nums">
          <div class="irn-item">
            <span class="irn-k">观众</span>
            <span class="irn-v" :class="{ missing: !it.visitor_count }">{{ fmtCount(it.visitor_count) }}</span>
          </div>
          <div class="irn-item">
            <span class="irn-k">展商</span>
            <span class="irn-v" :class="{ missing: !it.exhibitor_count }">{{ fmtCount(it.exhibitor_count) }}</span>
          </div>
          <div class="irn-item">
            <span class="irn-k">面积</span>
            <span class="irn-v" :class="{ missing: !it.exhibit_area_sqm }">
              {{ it.exhibit_area_sqm ? fmtCount(it.exhibit_area_sqm) + '㎡' : '—' }}
            </span>
          </div>
        </div>

        <!-- 右：结论 -->
        <div class="ir-verdict">
          <BandBadge
            :band="it.e1.band"
            :label="it.e1.label"
            :hint="it.e1.hint"
            :tone="e1Tone(it.e1.band)"
            :value="it.e1.ratio !== null ? fmtRatio(it.e1.ratio) : null"
            prefix="客群"
            size="sm"
          />
          <BandBadge
            :band="it.e4.band"
            :label="it.e4.label"
            :hint="it.e4.hint"
            :tone="e4Tone(it.e4.band)"
            prefix="展位"
            size="sm"
          />
        </div>
      </article>
    </div>

    <!-- 不要绑 @change：page/pageSize 的变化已经由 watch 接管。
         两边都绑会给同一个查询发两次一模一样的请求（实测确认过）。 -->
    <PaginationBar
      v-if="!loading && items.length"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      :total-pages="totalPages"
      :loading="loading"
      unit="场展会"
      :page-size-options="[20, 50, 100]"
      storage-key="expo-intel-page-size"
    />

    <p v-if="!loading && items.length" class="list-foot">
      比值 = 观众数 ÷ 展商数（每有个展位能分到多少观众）。缺一个数就算不出来，
      显示「无法判断」而不是 0——<strong>0 会被读成"一个观众都没有"</strong>。
    </p>
  </div>
</template>

<style scoped>
.intel-page {
  padding-top: var(--spacing-lg);
  padding-bottom: var(--spacing-xl);
}

/* ---------- 页头 ---------- */
.intel-head {
  display: flex;
  gap: var(--spacing-lg);
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  margin-bottom: var(--spacing-md);
}
.ih-main h1 {
  margin: 0 0 6px;
  font-size: var(--font-h2);
  font-weight: var(--weight-h2);
  color: var(--ink-900);
  letter-spacing: -0.02em;
}
.ih-sub {
  margin: 0;
  color: var(--ink-500);
  font-size: 14px;
}
.ih-sub strong {
  color: var(--ink-700);
}
.ih-calib {
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  min-width: 230px;
}
.ihc-line {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
}
.ihc-k {
  color: var(--ink-500);
}
.ihc-v {
  color: var(--brand-700);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.ihc-note {
  margin: 5px 0 0;
  font-size: 11px;
  line-height: 1.55;
  color: var(--ink-500);
}
.ihc-note strong {
  color: var(--brand-600);
}

/* ---------- 诚实条 ---------- */
.honesty-bar {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  background: #fffbeb;
  border: 1px solid #f5e2b5;
  border-left: 3px solid var(--accent-500);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  margin-bottom: var(--spacing-md);
}
.hb-icon {
  color: var(--accent-700);
  font-size: 14px;
  line-height: 1.5;
  flex-shrink: 0;
}
.hb-text {
  font-size: 12.5px;
  line-height: 1.65;
  color: #6b5316;
}
.hb-text strong {
  color: #513d0c;
}

/* ---------- 档位快筛 ---------- */
.chip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.chip-row-label {
  font-size: 12px;
  color: var(--ink-500);
  margin-right: 2px;
}
.chip-row-label.ml {
  margin-left: 10px;
}
.dist-chip {
  border: 1px solid var(--border-color);
  background: var(--surface-0);
  border-radius: var(--radius-full);
  padding: 3px 10px;
  font-size: 12px;
  color: var(--ink-700);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: all 0.14s ease;
}
.dist-chip b {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
.dist-chip:hover {
  border-color: var(--brand-300);
}
.dist-chip.active {
  box-shadow: inset 0 0 0 1.5px currentColor;
  font-weight: 700;
}
.dist-chip.tone-good { color: #0f7b52; }
.dist-chip.tone-neutral { color: var(--brand-600); }
.dist-chip.tone-warn { color: #96620b; }
.dist-chip.tone-bad { color: #a52a1f; }
.dist-chip.tone-live { color: #fff; background: var(--accent-600); border-color: var(--accent-700); }
.dist-chip.tone-muted { color: var(--ink-500); background: var(--surface-1); border-style: dashed; }

/* ---------- 筛选条 ---------- */
.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  background: var(--surface-0);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 10px 12px;
  margin-bottom: var(--spacing-md);
}
.fi-search,
.fi-select {
  height: 32px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 0 10px;
  font-size: 13px;
  color: var(--ink-900);
  background: var(--surface-0);
  outline: none;
}
.fi-search {
  flex: 1 1 200px;
  min-width: 160px;
}
.fi-search:focus,
.fi-select:focus {
  border-color: var(--brand-400);
}
.fi-check {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: var(--ink-700);
  cursor: pointer;
  user-select: none;
}
.fi-spacer {
  flex: 1 1 auto;
}
.sort-group {
  display: flex;
  gap: 4px;
  background: var(--surface-1);
  border-radius: var(--radius-md);
  padding: 3px;
}
.sort-btn {
  border: none;
  background: transparent;
  font-size: 12px;
  color: var(--ink-500);
  padding: 4px 9px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.sort-btn.active {
  background: var(--surface-0);
  color: var(--brand-600);
  font-weight: 700;
  box-shadow: var(--shadow-sm);
}
.sort-arrow {
  font-size: 10px;
}

/* ---------- 列表 ---------- */
.intel-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.intel-row {
  display: grid;
  /* 中间三列固定宽度：否则每行 auto 宽度随内容浮动，同一列的数字左右跳 */
  grid-template-columns: minmax(0, 1fr) 216px 178px;
  gap: 16px;
  align-items: center;
  background: var(--surface-0);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 12px 16px;
  cursor: pointer;
  transition: border-color 0.14s ease, box-shadow 0.14s ease, transform 0.14s ease;
}
.intel-row:hover {
  border-color: var(--brand-300);
  box-shadow: 0 2px 10px rgba(28, 68, 120, 0.08);
}
.intel-row:focus-visible {
  outline: 2px solid var(--brand-400);
  outline-offset: 2px;
}

.ir-title-line {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.ir-name {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-900);
  line-height: 1.4;
}
.ir-cat {
  font-size: 11px;
  color: var(--brand-600);
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  border-radius: var(--radius-sm);
  padding: 1px 6px;
}
.ir-src {
  font-size: 10.5px;
  color: #96620b;
  background: #fdf3e0;
  border: 1px solid #f2dcb2;
  border-radius: var(--radius-sm);
  padding: 1px 6px;
  cursor: help;
}
.ir-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-500);
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.ir-venue {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ir-date {
  font-variant-numeric: tabular-nums;
}

.ir-nums {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.irn-item {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 0;
}
.irn-k {
  font-size: 10.5px;
  color: var(--ink-300);
}
.irn-v {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-700);
  font-variant-numeric: tabular-nums;
}
.irn-v.missing {
  color: var(--ink-300);
  font-weight: 400;
}

.ir-verdict {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-end;
}

.list-foot {
  margin: var(--spacing-md) 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ink-500);
}
.list-foot strong {
  color: var(--ink-700);
}

/* ---------- 窄屏 ---------- */
@media (max-width: 860px) {
  .intel-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 8px;
  }
  .ir-nums {
    gap: 8px 14px;
  }
  .irn-item {
    align-items: flex-start;
  }
  .ir-verdict {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-start;
  }
  .ih-calib {
    width: 100%;
  }
}
</style>
