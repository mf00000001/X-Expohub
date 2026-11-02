<script setup lang="ts">
/**
 * 展会详情页
 *
 * 数据口径（2026-10-19 修复「展商/展品/展位/采购」与会展对不上）：
 * - 顶部统计条：GET /exhibitions/{id}/stats（名录真实聚合：展商/展品/城市/行业）
 * - 参展展商：GET /exhibitions/{id}/exhibitors（名录优先，分页 + total）
 * - 展品：GET /exhibitions/{id}/products（名录展品，分页，无图用 ExpoCover 兜底）
 * - 展位：只有真实展位数据才显示整块（booths 已随旧 seed 清空，不展示空表）
 * - 采购需求：GET /procurements?exhibition_id=（后端已按展会过滤，空就直说空）
 * 页面不编造任何数字：接口失败时统计条隐藏，列表为空时展示明确文案。
 */
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import ExpoCover from '@/components/ExpoCover.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { exhibitionApi } from '@/api/exhibition'
import type {
  ExhibitionStats,
  ExhibitionExhibitorItem,
  ExhibitionProductItem,
} from '@/api/exhibition'
import { boothApi } from '@/api/booth'
import { registrationApi } from '@/api/registration'
import { useUserStore } from '@/stores/user'
import { useI18n } from '@/composables/useI18n'
import http from '@/api/index'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { pick } = useI18n()

const exhibitionId = computed(() => Number(route.params.id))
const exhibition = ref<Record<string, any> | null>(null)
const loading = ref(true)
const registered = ref(false)

/** 顶部统计条（/stats）：失败为 null → 整条隐藏，不显示 0 冒充数据 */
const stats = ref<ExhibitionStats | null>(null)

/** 展位：真实数据为空时整块（tab + 面板）都不渲染 */
const booths = ref<any[]>([])
const showBooths = computed(() => booths.value.length > 0)

/** 参展展商（名录优先，分页） */
const exhibitors = ref<ExhibitionExhibitorItem[]>([])
const exhTotal = ref(0)
const exhPage = ref(1)
const exhPageSize = ref(12)
const exhLoading = ref(false)
const exhLoaded = ref(false)

/** 展品（名录展品，分页） */
const catalogProducts = ref<ExhibitionProductItem[]>([])
const prodTotal = ref(0)
const prodPage = ref(1)
const prodPageSize = ref(12)
const prodLoading = ref(false)
const prodLoaded = ref(false)

/** 采购需求（后端按 exhibition_id 过滤；无需求 → 空列表 + total 0） */
const procurements = ref<any[]>([])
const procTotal = ref(0)

type TabKey = 'booths' | 'exhibitors' | 'products' | 'procurements'
const tab = ref<TabKey>('exhibitors')

/** 数字展示：千分位；null/NaN 一律显示 0（数据本身就是 0 时才显示 0） */
const fmtNum = (n: number | null | undefined): string => {
  const v = Number(n)
  return Number.isFinite(v) ? v.toLocaleString('zh-CN') : '0'
}

// 展商字段兼容两种口径：名录（name/industry/city/product_count）与展位回落（company/...）
const exhibitorName = (e: ExhibitionExhibitorItem): string => e.name || e.company || '—'
const exhibitorIndustry = (e: ExhibitionExhibitorItem): string => e.industry || e.industry_domain || ''
const exhibitorCity = (e: ExhibitionExhibitorItem): string => e.city || e.region || ''
const exhibitorProducts = (e: ExhibitionExhibitorItem): number =>
  Number(e.product_count ?? e.products_count ?? 0)
// 名录类目是逗号分隔的多值（如「机床工具,模具制造」），标签里只取第一个
const productCategory = (p: ExhibitionProductItem): string => (p.category || '').split(',')[0]

async function fetchStats() {
  stats.value = await exhibitionApi.getStats(exhibitionId.value)
}

async function fetchBooths() {
  const r: any = await boothApi
    .getList({ exhibition_id: exhibitionId.value, page_size: 50 })
    .catch(() => null)
  booths.value = (r && (r.list || r.items)) || []
}

async function fetchExhibitors() {
  exhLoading.value = true
  try {
    const r = await exhibitionApi.getExhibitors(exhibitionId.value, {
      page: exhPage.value,
      page_size: exhPageSize.value,
    })
    exhibitors.value = r.list || []
    exhTotal.value = Number(r.total ?? exhibitors.value.length)
    exhLoaded.value = true
  } finally {
    exhLoading.value = false
  }
}

async function fetchProducts() {
  prodLoading.value = true
  try {
    const r = await exhibitionApi.getProducts(exhibitionId.value, {
      page: prodPage.value,
      page_size: prodPageSize.value,
    })
    catalogProducts.value = r.list || []
    prodTotal.value = Number(r.total ?? catalogProducts.value.length)
    prodLoaded.value = true
  } finally {
    prodLoading.value = false
  }
}

async function fetchProcurements() {
  try {
    const r: any = await http.get('/procurements', {
      params: { exhibition_id: exhibitionId.value, page_size: 20 },
    })
    const body = r || {}
    procurements.value = body.list || body.items || []
    procTotal.value = Number(body.total ?? procurements.value.length)
  } catch {
    // 接口失败按「无需求」处理：不展示别的展会的需求，也不留空白
    procurements.value = []
    procTotal.value = 0
  }
}

function switchTab(t: TabKey) {
  tab.value = t
  if (t === 'exhibitors' && !exhLoaded.value) fetchExhibitors()
  if (t === 'products' && !prodLoaded.value) fetchProducts()
}

const title = computed(() => pick(exhibition.value, 'title') || exhibition.value?.name || '')
const cover = computed(() => exhibition.value?.cover_image || exhibition.value?.cover_url || '')
const startDate = computed(() => exhibition.value?.start_date || exhibition.value?.startDate || '')
const endDate = computed(() => exhibition.value?.end_date || exhibition.value?.endDate || '')
const location = computed(() => exhibition.value?.location || exhibition.value?.venue || '')
// V3.1: 关联展馆(可点击跳转展馆信息页)
const venueId = computed(() => (exhibition.value as any)?.venue_info?.id || null)
const orgName = computed(() => exhibition.value?.organizer_name || exhibition.value?.organizerName || '')
const orgId = computed(() => exhibition.value?.organizer_id)
const desc = computed(() => pick(exhibition.value, 'description') || '')
const status = computed(() => exhibition.value?.status || '')

onMounted(async () => {
  try {
    const [expRes] = await Promise.all([
      exhibitionApi.getDetail(exhibitionId.value),
      fetchStats(),
      fetchBooths(),
      fetchProcurements(),
    ])
    exhibition.value = expRes
    // 没有真实展位就不进「展位」tab（整块隐藏），默认落到展商
    tab.value = showBooths.value ? 'booths' : 'exhibitors'
    // 首屏就取回两个区块第一页：tab 上的数字与列表同源，不会一个真一个假
    await Promise.all([fetchExhibitors(), fetchProducts()])
  } catch (err) {
    console.error('Failed to load exhibition:', err)
  } finally {
    loading.value = false
  }
})

async function handleRegister() {
  if (!userStore.isLoggedIn) {
    router.push('/login')
    return
  }
  try {
    await registrationApi.register({ exhibition_id: Number(route.params.id) })
    registered.value = true
    showToast('报名成功!')
  } catch (err: any) {
    showToast('报名失败', 'error')
  }
}

function showToast(msg: string, type = 'success') {
  const t = document.createElement('div')
  t.className = 'toast toast-' + type
  t.textContent = msg
  document.body.appendChild(t)
  setTimeout(() => t.remove(), 3000)
}

function goToBooth(id: number) {
  router.push('/booths/' + id)
}
async function applyBooth(bid: number) {
  if (!userStore.isLoggedIn) {
    router.push('/login')
    return
  }
  try {
    await http.post('/booths/' + bid + '/apply')
    alert('申请已提交！')
  } catch (e: any) {
    alert(e?.response?.data?.message || '申请失败')
  }
}
function canRegister(s: string) {
  return s === 'published' || s === 'ongoing'
}
function goToTickets() {
  router.push(`/exhibitions/${route.params.id}/tickets`)
}

const statusMap: Record<string, string> = {
  draft: '草稿',
  pending: '待审核',
  published: '已发布',
  ongoing: '进行中',
  ended: '已结束',
  cancelled: '已取消',
}
// 时间线标签：按日期推导，往届展会显示"已结束"而非编辑状态"已发布"
const timelineLabel = computed(() => {
  const st = startDate.value ? new Date(startDate.value).getTime() : NaN
  const en = endDate.value ? new Date(endDate.value).getTime() : NaN
  if (!Number.isFinite(st) || !Number.isFinite(en)) return ''
  const now = Date.now()
  if (now < st) return '即将举办'
  if (now > en) return '已结束'
  return '进行中'
})
const statusClass = computed(() => {
  if (timelineLabel.value === '进行中') return 'tag-success'
  if (timelineLabel.value === '即将举办') return 'tag-warning'
  if (timelineLabel.value === '已结束') return 'tag-info'
  if (status.value === 'published' || status.value === 'ongoing') return 'tag-success'
  if (status.value === 'pending') return 'tag-warning'
  return 'tag-info'
})
// 日期精简显示（YYYY-MM-DD），避免原始 ISO 串进界面
const fmtDate = (d: string) => (d || '').slice(0, 10)
</script>

<template>
<div>
<div class="container page-wrapper" v-if="loading"><LoadingSkeleton :lines="8"/></div>
<div v-else-if="!exhibition" class="container page-wrapper"><p>展会不存在</p></div>
<div v-else class="container page-wrapper">
  <div class="breadcrumb">
    <router-link to="/">首页</router-link><span>/</span>
    <router-link to="/exhibitions">展会</router-link><span>/</span>
    <span>{{ title }}</span>
  </div>

  <!-- 真实统计条：展商 N · 展品 M · 覆盖城市 K · 行业 J（来自 /stats，失败则整条隐藏） -->
  <div v-if="stats" class="stats-strip">
    <span class="stat-item">展商 <strong>{{ fmtNum(stats.exhibitors) }}</strong></span>
    <span class="stat-sep">·</span>
    <span class="stat-item">展品 <strong>{{ fmtNum(stats.products) }}</strong></span>
    <span class="stat-sep">·</span>
    <span class="stat-item">覆盖城市 <strong>{{ fmtNum(stats.cities) }}</strong></span>
    <span class="stat-sep">·</span>
    <span class="stat-item">行业 <strong>{{ fmtNum(stats.industries) }}</strong></span>
  </div>

  <!-- Hero -->
  <div class="detail-hero" v-if="cover">
    <img :src="cover" :alt="title" />
    <div class="hero-overlay">
      <span class="tag" :class="statusClass">{{ timelineLabel || statusMap[status] || status }}</span>
      <h1>{{ title }}</h1>
      <div class="hero-meta">
        <span>📅 {{ fmtDate(startDate) }} ~ {{ fmtDate(endDate) }}</span>
        <router-link v-if="venueId" :to="'/venues/' + venueId" class="venue-link">📍 {{ location }} <span class="venue-tag">展馆信息 ›</span></router-link>
        <span v-else>📍 {{ location }}</span>
        <span v-if="orgName" class="platform-operator">👤 运营方：{{ orgName }}</span>
        <!-- 展位/展商数只在有真实数据时展示，不再出现「0 个展位」 -->
        <span v-if="showBooths">🏢 {{ booths.length }} 个展位</span>
        <span v-if="stats && stats.exhibitors">🧑‍💼 {{ fmtNum(stats.exhibitors) }} 家展商</span>
      </div>
    </div>
  </div>

  <!-- No cover fallback -->
  <div v-else class="card card-body mb-4">
    <div class="flex justify-between items-start">
      <h1>{{ title }}</h1>
      <span class="tag" :class="statusClass">{{ timelineLabel || statusMap[status] || status }}</span>
    </div>
    <div class="meta-row">
      <span>📅 {{ fmtDate(startDate) }} ~ {{ fmtDate(endDate) }}</span>
      <router-link v-if="venueId" :to="'/venues/' + venueId" class="venue-link">📍 {{ location }} <span class="venue-tag">展馆信息 ›</span></router-link>
      <span v-else>📍 {{ location }}</span>
      <span v-if="orgName">👤 运营方：{{ orgName }}</span>
      <span v-if="showBooths">🏢 {{ booths.length }} 个展位</span>
      <span v-if="stats && stats.exhibitors">🧑‍💼 {{ fmtNum(stats.exhibitors) }} 家展商</span>
    </div>
  </div>

  <!-- Description -->
  <div class="card card-body mb-4" v-if="desc">
    <h3 class="section-title">📋 展会简介</h3>
    <p class="desc-text">{{ desc }}</p>
    <button v-if="canRegister(status)" class="btn btn-primary btn-lg mt-4" @click="handleRegister">
      {{ registered ? '已报名' : '立即报名参展' }}
    </button>
    <button v-if="canRegister(status)" class="btn btn-outline btn-lg mt-4 ml-sm" @click="goToTickets" style="margin-left:8px">
      🎫 购买门票
    </button>
  </div>

  <!-- Tabs: Booths(仅真实数据) / Exhibitors / Products / Procurements -->
  <div class="card mb-4">
    <div class="tab-header">
      <button v-if="showBooths" :class="['tab-btn', {active:tab==='booths'}]" @click="switchTab('booths')">🏢 展位 ({{ booths.length }})</button>
      <button :class="['tab-btn', {active:tab==='exhibitors'}]" @click="switchTab('exhibitors')">🧑‍💼 参展展商 ({{ fmtNum(exhLoaded ? exhTotal : (stats?.exhibitors || 0)) }})</button>
      <button :class="['tab-btn', {active:tab==='products'}]" @click="switchTab('products')">📦 展品 ({{ fmtNum(prodLoaded ? prodTotal : (stats?.products || 0)) }})</button>
      <button :class="['tab-btn', {active:tab==='procurements'}]" @click="switchTab('procurements')">📋 采购需求 ({{ fmtNum(procTotal) }})</button>
    </div>

    <!-- Booths：无真实展位数据时整块隐藏（tab 都不渲染），不留空表 -->
    <div v-if="showBooths && tab==='booths'" class="card-body">
      <div class="booth-grid">
        <div v-for="b in booths" :key="b.id" class="booth-card" @click="goToBooth(b.id)">
          <div class="booth-header">
            <span class="booth-num">{{ b.booth_number }}</span>
            <span class="tag tag-sm" :class="b.status==='occupied'?'tag-success':b.status==='available'?'tag-info':'tag-warning'">
              {{ b.status==='occupied'?'已入驻':b.status==='available'?'可预订':b.status }}
            </span>
          </div>
          <p class="booth-company" v-if="b.company_name">{{ b.company_name }}</p>
            <button v-if="b.status==='available'" class="btn btn-sm btn-primary-outline" @click.stop="applyBooth(b.id)" style="margin-top:6px">申请入驻</button>
          <div class="booth-info">
            <span v-if="b.size">面积: {{ b.size }}</span>
            <span v-if="b.location_area">{{ b.location_area }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Exhibitors 参展展商（真实公司名/行业/城市/展品数 + 分页） -->
    <div v-if="tab==='exhibitors'" class="card-body">
      <!-- 名录深链：本 tab 只展示前几页，完整名录去 /catalog/exhibitors（按展会作用域） -->
      <div class="exh-more-bar">
        <span class="exh-more-hint">共 {{ fmtNum(exhLoaded ? exhTotal : (stats?.exhibitors || 0)) }} 家参展展商</span>
        <router-link
          class="exh-more-link"
          :to="{ name: 'catalog-exhibitors', query: { exhibition_id: exhibitionId } }"
        >在展商名录中查看 ›</router-link>
      </div>
      <div v-if="exhLoading && exhibitors.length===0" class="empty-hint">加载中…</div>
      <div v-else-if="exhibitors.length===0" class="empty-hint">该展会暂无名录展商</div>
      <template v-else>
        <div class="exh-grid">
          <div v-for="(e, i) in exhibitors" :key="e.exhibitor_id ?? i" class="exh-card">
            <div class="exh-name">{{ exhibitorName(e) }}</div>
            <div class="exh-tags">
              <span v-if="exhibitorIndustry(e)" class="tag tag-sm tag-info">🏷️ {{ exhibitorIndustry(e) }}</span>
              <span v-if="exhibitorCity(e)" class="tag tag-sm tag-primary">📍 {{ exhibitorCity(e) }}</span>
            </div>
            <div class="exh-sub">
              <span v-if="exhibitorProducts(e)">📦 {{ exhibitorProducts(e) }} 件展品</span>
              <span v-else>暂未登记展品</span>
            </div>
          </div>
        </div>
        <PaginationBar
          v-model:page="exhPage"
          v-model:page-size="exhPageSize"
          :total="exhTotal"
          :loading="exhLoading"
          unit="家展商"
          :page-size-options="[12, 24, 48]"
          storage-key="exhibition-exhibitors-size"
          @change="fetchExhibitors"
        />
      </template>
    </div>

    <!-- Products 名录展品（网格；无图用 ExpoCover 兜底） -->
    <div v-if="tab==='products'" class="card-body">
      <div v-if="prodLoading && catalogProducts.length===0" class="empty-hint">加载中…</div>
      <div v-else-if="catalogProducts.length===0" class="empty-hint">该展会暂无名录展品</div>
      <template v-else>
        <div class="prod-grid">
          <div v-for="p in catalogProducts" :key="p.id" class="prod-card" @click="router.push('/catalog/products/'+p.id)">
            <div class="prod-cover">
              <ExpoCover :src="p.image || ''" :title="p.name" ratio="4/3" :alt="p.name" />
            </div>
            <div class="prod-name" :title="p.name">{{ p.name }}</div>
            <div class="prod-sub">
              <span v-if="productCategory(p)" class="tag tag-sm tag-info">{{ productCategory(p) }}</span>
              <span v-if="p.exhibitor_name" class="prod-exh" :title="p.exhibitor_name">{{ p.exhibitor_name }}</span>
            </div>
          </div>
        </div>
        <PaginationBar
          v-model:page="prodPage"
          v-model:page-size="prodPageSize"
          :total="prodTotal"
          :loading="prodLoading"
          unit="件展品"
          :page-size-options="[12, 24, 48]"
          storage-key="exhibition-products-size"
          @change="fetchProducts"
        />
      </template>
    </div>

    <!-- Procurements 采购需求（无需求时明确文案，不空白、不伪造） -->
    <div v-if="tab==='procurements'" class="card-body">
      <div v-if="procurements.length===0" class="empty-hint">该展会暂无采购需求</div>
      <div v-else class="proc-list">
        <div v-for="p in procurements" :key="p.id" class="proc-item" @click="router.push('/procurements/'+p.id)">
          <div class="proc-left"><strong>{{ p.title }}</strong><span class="proc-cat">{{ p.category }}</span></div>
          <span class="tag" :class="p.status==='pending'?'tag-warning':'tag-info'">{{ p.status==='pending'?'待匹配':'已匹配' }}</span>
        </div>
      </div>
    </div>
  </div>
</div>
</div>
</template>

<style scoped>
.detail-hero { position:relative; height:320px; overflow:hidden; border-radius:12px; margin-bottom:16px }
.detail-hero img { width:100%; height:100%; object-fit:cover }
.hero-overlay { position:absolute; bottom:0; left:0; right:0; padding:40px 24px 24px; background:linear-gradient(transparent,rgba(0,0,0,0.75)); color:#fff }
.hero-overlay h1 { font-size:28px; font-weight:700; margin:8px 0 }
.hero-meta { display:flex; gap:20px; flex-wrap:wrap; font-size:14px; opacity:0.9 }
.meta-row { display:flex; gap:20px; flex-wrap:wrap; font-size:14px; color:#666; margin-top:8px }
.section-title { font-size:18px; font-weight:600; margin-bottom:12px }
.desc-text { line-height:1.9; color:#555; white-space:pre-wrap }
/* 顶部真实统计条（/stats）：一行、可换行、数字加粗 */
.stats-strip { display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px; margin:0 0 16px; padding:10px 16px; border:1px solid #e5e7eb; border-radius:8px; background:#f8fafc; font-size:14px; color:#4b5563 }
.stats-strip .stat-item { white-space:nowrap }
.stats-strip strong { color:#1f2937; font-size:16px; font-variant-numeric:tabular-nums }
.stats-strip .stat-sep { color:#cbd5e1 }
.tab-header { display:flex; border-bottom:1px solid #e5e7eb }
.tab-btn { flex:1; padding:14px; border:none; background:none; font-size:15px; font-weight:500; cursor:pointer; color:#666; border-bottom:2px solid transparent; transition:all .2s }
.tab-btn.active { color:#2563eb; border-bottom-color:#2563eb; background:#eff6ff }
.booth-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:12px }
.booth-card { padding:16px; border:1px solid #e5e7eb; border-radius:8px; cursor:pointer; transition:all .2s }
.booth-card:hover { border-color:#2563eb; box-shadow:0 2px 8px rgba(37,99,235,0.1) }
.booth-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px }
.booth-num { font-weight:700; font-size:16px; color:#1f2937 }
.booth-company { font-size:14px; color:#2563eb; margin-bottom:6px }
.booth-info { display:flex; gap:12px; font-size:12px; color:#888; flex-wrap:wrap }
.empty-hint { text-align:center; padding:40px; color:#999 }
.tag-sm { font-size:11px; padding:2px 6px }
/* 参展展商名录（真实名录数据） */
/* 名录深链条：本页只展示前几页，完整名录去 /catalog/exhibitors?exhibition_id= */
.exh-more-bar { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:12px; padding:10px 14px; background:#f5f8ff; border:1px solid #dbe6fb; border-radius:8px }
.exh-more-hint { font-size:13px; color:#374151 }
.exh-more-link { font-size:13px; font-weight:600; color:#2563eb; text-decoration:none; white-space:nowrap }
.exh-more-link:hover { text-decoration:underline }
.exh-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:12px }
.exh-card { padding:14px; border:1px solid #e5e7eb; border-radius:8px; transition:all .2s }
.exh-card:hover { border-color:#2563eb; box-shadow:0 2px 8px rgba(37,99,235,0.1) }
.exh-name { font-weight:600; font-size:14px; color:#1f2937; margin-bottom:8px; line-height:1.4 }
.exh-tags { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:6px }
.exh-sub { display:flex; gap:12px; font-size:12px; color:#888; flex-wrap:wrap }
/* 展品网格：图片位固定 4:3，无图时由 ExpoCover 出品牌渐变兜底 */
.prod-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:14px }
.prod-card { border:1px solid #e5e7eb; border-radius:8px; overflow:hidden; cursor:pointer; transition:all .2s; background:#fff }
.prod-card:hover { border-color:#2563eb; box-shadow:0 2px 10px rgba(37,99,235,0.12) }
.prod-cover { border-radius:0 }
.prod-name { padding:8px 10px 2px; font-size:14px; font-weight:600; color:#1f2937; line-height:1.4; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden }
.prod-sub { display:flex; gap:6px; flex-wrap:wrap; align-items:center; padding:6px 10px 10px; font-size:12px; color:#888 }
.prod-exh { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100% }
.btn-lg { padding:12px 32px; font-size:16px }
/* V3.1: 展馆链接 */
.venue-link { color:inherit; text-decoration:none; border-bottom:1px dashed rgba(255,255,255,0.6); cursor:pointer }
.meta-row .venue-link { border-bottom-color:#bbb }
.venue-link:hover { opacity:0.8 }
.venue-tag { font-size:11px; background:#2563eb; color:#fff; border-radius:4px; padding:1px 6px; margin-left:4px; vertical-align:middle }
@media(max-width:640px) { .detail-hero { height:200px } .hero-overlay h1 { font-size:20px } }
</style>
