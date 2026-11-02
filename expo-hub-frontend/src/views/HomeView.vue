<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import HeroBanner from '@/components/HeroBanner.vue'
import TrustStrip from '@/components/TrustStrip.vue'
import MagazineExpoCard from '@/components/MagazineExpoCard.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import CategoryGrid from '@/components/CategoryGrid.vue'
import ActivityFeed from '@/components/ActivityFeed.vue'
import HallOfFame from '@/components/HallOfFame.vue'
import UpcomingExhibitions from '@/components/UpcomingExhibitions.vue'
import HotProducts from '@/components/HotProducts.vue'
import CompanyAvatar from '@/components/CompanyAvatar.vue'
import { catalogApi } from '@/api/catalog'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import { exhibitionApi, type Exhibition, type HallOfFameItem } from '@/api/exhibition'
import { getPublicStats, formatStat, type PublicStats } from '@/api/stats'
import http from '@/api/index'
import { useUserStore } from '@/stores/user'

function tierIcon(t?: string) {
  return ({ free: '🆓', regular: '⭐', flagship: '👑' } as Record<string, string>)[t || 'free'] || '🆓'
}

const userStore = useUserStore()

const router = useRouter()
const featured = ref<Exhibition[]>([])
const hot = ref<Exhibition[]>([])
// 「重磅发布」数据源：即将举办的展会（后端 limit 上限 100，一次取满，前端切片「查看更多」）
const upcoming = ref<Exhibition[]>([])
// 「全球标杆展会」数据源：≤10 场，接口失败/空数据时整块隐藏（由 HallOfFame 内部兜底）
const hallOfFame = ref<HallOfFameItem[]>([])
const hotMB = ref<any[]>([])
const loading = ref(true)
const searchKeyword = ref('')
// 首页公开统计（真实接口 /stats/public；失败为 null，页面显示「—」而不是编造数字）
const stats = ref<PublicStats | null>(null)
// 可信度数字条的补充两项：展馆覆盖城市来自 GET /venues 的展馆去重城市数，
// 行业品类来自 GET /categories 标准清单。拿不到就保持 0，TrustStrip 会整项不渲染（不估算、不回填）。
const venueCityCount = ref(0)
const categoryCount = ref(0)

/** /venues 返回 { list } / { data: { list } } / 裸数组，三种都兼容，只数去重后的城市 */
function distinctCities(resp: any): number {
  const list = Array.isArray(resp) ? resp : (resp?.list ?? resp?.data?.list ?? [])
  if (!Array.isArray(list)) return 0
  const cities = new Set<string>()
  for (const v of list) {
    const city = String(v?.city ?? '').trim()
    if (city) cities.add(city)
  }
  return cities.size
}

/** /categories 返回 { categories: [string] }；只数有名字的品类 */
function countCategories(resp: any): number {
  const list = resp?.categories ?? resp?.data?.categories
  if (!Array.isArray(list)) return 0
  return list.filter((c: any) => {
    const name = typeof c === 'string' ? c : c?.name
    return typeof name === 'string' && name.trim().length > 0
  }).length
}

/** 补充计数单独请求，不阻塞首屏：这两个接口慢时数字条晚一点出现，不影响 Hero 与精选区 */
async function loadTrustCounts() {
  const [catalogStats, catResp] = await Promise.all([
    catalogApi.getStats(),
    http.get('/categories').catch(() => null),
  ])
  // 城市数改用名录口径：真实展会实际覆盖的城市（展馆库里的 20 个城市并不等于办过展的城市）
  venueCityCount.value = Number(catalogStats?.cities) || 0
  categoryCount.value = countCategories(catResp)
}

onMounted(async () => {
  loading.value = true
  try {
    const [f, h, u, hof, mb, s] = await Promise.all([
      exhibitionApi.getFeatured(5),
      exhibitionApi.getHot(10),
      exhibitionApi.getUpcoming(100),
      exhibitionApi.getHallOfFame(),
      http.get('/micro-booths?page_size=6').catch(()=>({list:[]})),
      getPublicStats(),
    ])
    featured.value = f || []
    hot.value = h || []
    upcoming.value = u || []
    hallOfFame.value = hof || []
    hotMB.value = (mb as any)?.list || (mb as any)?.data?.list || []
    stats.value = s
  } catch (e) {
    console.error('Failed to load homepage data:', e)
  } finally {
    loading.value = false
  }
  void loadTrustCounts()
})

/**
 * 精选区排序口径：与 Hero 轮播同一套状态推导（日期优先、status 兜底），两处排序与徽章保持一致。
 * 即将开幕 → 进行中 → 已结束：已结束排到末尾，不再占据大卡位置。
 */
type FeaturedStatus = 'upcoming' | 'ongoing' | 'ended'
const FEATURED_RANK: Record<FeaturedStatus, number> = { upcoming: 0, ongoing: 1, ended: 2 }

/** 日期解析：缺失/非法一律返回 null（不把坏数据当成「今天」） */
function parseDate(value?: string): Date | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isFinite(d.getTime()) ? d : null
}

function featuredStatusOf(e: any): FeaturedStatus {
  const now = Date.now()
  const end = parseDate(e?.end_date || e?.endDate)
  const start = parseDate(e?.start_date || e?.startDate)
  if (end && now > end.getTime()) return 'ended'
  if (start && now >= start.getTime()) return 'ongoing'
  if (start) return 'upcoming'
  const st = String(e?.status || '')
  if (st === 'ongoing') return 'ongoing'
  if (st === 'finished' || st === 'ended' || st === 'cancelled') return 'ended'
  return 'upcoming'
}

/**
 * 排序细节：同组内「越早开幕越靠前」，已结束「越近结束越靠前」，
 * 日期缺失的排到同组末尾，日期相同则保持接口原顺序（稳定、可预期）。
 */
const featuredSorted = computed<Exhibition[]>(() => {
  const rows = (featured.value ?? []).map((e, idx) => {
    const start = parseDate((e as any)?.start_date || (e as any)?.startDate)
    return { e, idx, status: featuredStatusOf(e), ts: start ? start.getTime() : null }
  })
  rows.sort((a, b) => {
    if (FEATURED_RANK[a.status] !== FEATURED_RANK[b.status]) {
      return FEATURED_RANK[a.status] - FEATURED_RANK[b.status]
    }
    if (a.ts === null && b.ts === null) return a.idx - b.idx
    if (a.ts === null) return 1
    if (b.ts === null) return -1
    if (a.ts === b.ts) return a.idx - b.idx
    return a.status === 'ended' ? b.ts - a.ts : a.ts - b.ts
  })
  return rows.map((r) => r.e)
})

function goToExhibition(id: number) {
  router.push({ name: 'exhibition-detail', params: { id } })
}
function goToCategory(cat: string) {
  router.push({ name: 'search', query: { cat: cat } })
}
function handleSearch(v: string) {
  if (v.trim()) router.push({ name: 'search', query: { q: v.trim() } })
}
</script>

<template>
  <div class="home-v2">
    <!-- 1. 首屏：品牌深蓝 Hero + 轮播 + 实时数据带（轮播内部只保留即将开幕/进行中，已结束仅兜底） -->
    <HeroBanner :exhibitions="featuredSorted" :stats="stats" @goto="goToExhibition" />

    <!-- 2. 可信度数字条：紧随 Hero，四项都不可用时整条不渲染；
         口径与 Hero 数据带错开：展馆覆盖城市 / 行业品类 / 微展位在线 / 采购需求 -->
    <TrustStrip :stats="stats" :venue-city-count="venueCityCount" :category-count="categoryCount" />

    <div class="home-body">
      <!-- 3. 工具条：搜索 + 登录后的 AI 入口 -->
      <div class="utility">
        <div class="search-row">
          <SearchBar v-model="searchKeyword" placeholder="搜索展会、展商、展品..." :live="false" @search="handleSearch" />
        </div>
        <router-link v-if="userStore.isLoggedIn" to="/ai/lab" class="ai-lab-entry">
          <span class="ai-lab-icon">✨</span>
          <span class="ai-lab-text"><strong>AI 实验室</strong> 文案生成 · 翻译 · 采购匹配建议</span>
          <span class="ai-lab-go">›</span>
        </router-link>
      </div>

      <!-- 4. 精选展会：杂志式「1 大 + 2 小」，无 featured 数据整块隐藏。
           条目按 featuredSorted 排过序：即将开幕/进行中在大卡与小卡前列，已结束排末尾 -->
      <section class="section featured" v-if="featuredSorted.length > 0">
        <div class="section-head">
          <div class="section-heading">
            <h2>精选展会</h2>
            <p class="section-sub">按展期挑一场，先定行程再谈生意</p>
          </div>
          <router-link class="section-more" :to="{ name: 'exhibition-list' }">查看全部 →</router-link>
        </div>
        <div class="featured-grid" :class="{ single: featuredSorted.length === 1 }">
          <MagazineExpoCard :exhibition="featuredSorted[0]" variant="large" @click="goToExhibition" />
          <div class="featured-side" v-if="featuredSorted.length > 1">
            <MagazineExpoCard
              v-for="e in featuredSorted.slice(1, 3)"
              :key="e.id"
              :exhibition="e"
              variant="small"
              @click="goToExhibition"
            />
          </div>
        </div>
      </section>

      <!-- 5. 重磅发布：按月份分组的纵向时间轴（保留「查看更多」与空态规则） -->
      <UpcomingExhibitions :list="upcoming" @goto="goToExhibition" />

      <!-- 6. 全球标杆展会（≤10 场，接口空/失败整块隐藏）
           精选条目不在 exhibitions 表里，卡片不可点击，故不监听 goto 跳详情 -->
      <HallOfFame :list="hallOfFame" />

      <!-- 7. 热门微展位 -->
      <section class="section" v-if="hotMB.length > 0">
        <div class="section-head">
          <div class="section-heading">
            <h2>🔥 热门微展位</h2>
            <p class="section-sub">这些展商正在获得买家关注</p>
          </div>
          <router-link class="section-more" :to="{ name: 'micro-booth-list' }">查看全部 →</router-link>
        </div>
        <div class="hotmb-row">
          <div v-for="mb in hotMB.slice(0,4)" :key="mb.id" class="hotmb-card" @click="$router.push('/micro-booths/'+mb.id)">
            <!-- 无 logo 时用公司名哈希色块 + 首字，卡片不再只有一行文字 -->
            <div class="hotmb-top">
              <CompanyAvatar :name="mb.name || ''" :src="mb.logo_url || ''" :size="38" />
              <div class="hotmb-main">
                <span class="hotmb-tier">{{ tierIcon(mb.membership_tier) }}</span>
                <strong :title="mb.name">{{ mb.name?.slice(0,20) }}</strong>
              </div>
            </div>
            <div class="hotmb-stats">
              <span>👀{{ mb.view_count }}</span>
              <span>❤️{{ mb.favorite_count }}</span>
              <span>📦{{ mb.product_count }}展品</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 8. 行业分类 -->
      <section class="section">
        <div class="section-head">
          <div class="section-heading">
            <h2>🏷️ 按行业找展品</h2>
            <p class="section-sub">按品类筛一遍，找供应商更快</p>
          </div>
          <router-link class="section-more" :to="{ name: 'product-list' }">查看全部 →</router-link>
        </div>
        <CategoryGrid @select="goToCategory" />
      </section>

      <!-- 9. 热门展会 -->
      <section class="section" v-if="hot.length > 0">
        <div class="section-head">
          <div class="section-heading">
            <h2>📈 热门展会</h2>
            <p class="section-sub">大家在看的展会</p>
          </div>
          <router-link class="section-more" :to="{ name: 'exhibition-list' }">查看全部 →</router-link>
        </div>
        <div class="card-grid-3">
          <ExpoCard v-for="e in hot.slice(0, 6)" :key="e.id" :exhibition="e" @click="goToExhibition(e.id)" />
        </div>
      </section>

      <!-- 10. 热门展品：第三方公开名录（组件内部取数，失败或空则整块不渲染） -->
      <HotProducts />

      <!-- 11. 转化区：展商 / 采购商两栏，深蓝卡片 + 金色按钮（放在实时动态之前） -->
      <section class="convert" aria-label="展商与采购商入口">
        <div class="convert-card">
          <p class="convert-kicker">展商</p>
          <h2 class="convert-title">我是展商，免费入驻</h2>
          <p class="convert-sub">把展品挂上首页，先让买家刷到你</p>
          <p class="convert-meta">
            {{ formatStat(stats?.exhibitors) }} 家展商已入驻 · {{ formatStat(stats?.products) }} 件展品展示
          </p>
          <router-link class="convert-btn" to="/register">免费开通微展位</router-link>
        </div>
        <div class="convert-card">
          <p class="convert-kicker">采购商</p>
          <h2 class="convert-title">我是买家，寻找供应商</h2>
          <p class="convert-sub">收藏展商、约见展会、发布采购需求，一个入口搞定</p>
          <p class="convert-meta">{{ formatStat(stats?.micro_booths) }} 个微展位在线</p>
          <router-link class="convert-btn" to="/micro-booths">浏览供应商</router-link>
        </div>
      </section>

      <!-- 12. 实时动态：独立区块，放在页面底部（移动端自然排在页面末尾） -->
      <ActivityFeed :recent="stats?.recent" />
    </div>

    <LoadingSkeleton v-if="loading" type="list" :count="6" />
  </div>
</template>

<style scoped>
.home-v2 { background: var(--surface-0); min-height: 100vh; }
/* 侧边栏已取消（实时动态改为页面底部的独立区块），主内容单列居中 */
.home-body {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-7) var(--space-5) var(--space-8);
}

/* 区块之间垂直留白 48px，一屏不超过两个主题 */
.section { margin-bottom: var(--space-7); }
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}
.section-heading { min-width: 0; }
.section-head h2 {
  font-size: var(--font-h2);
  line-height: var(--line-h2);
  font-weight: var(--weight-h2);
  color: var(--ink-900);
  letter-spacing: -0.01em;
}
.section-sub {
  margin-top: var(--space-1);
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: var(--ink-500);
}
.section-more {
  flex-shrink: 0;
  font-size: var(--font-sm);
  font-weight: 600;
  color: var(--brand-600);
  transition: color 0.15s ease;
}
.section-more:hover { color: var(--brand-800); }

/* 工具条：搜索 + AI 入口 */
.utility {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-bottom: var(--space-7);
}
.search-row {
  padding: var(--space-3);
  background: var(--surface-1);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
}

/* 精选展会：左大右两小。
   align-items: stretch 让右列跟随大卡高度；右侧不足 2 条时由 flex:1 把剩余高度吃满，不留白 */
.featured-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr);
  gap: var(--space-4);
  align-items: stretch;
}
.featured-grid.single { grid-template-columns: minmax(0, 1fr); }
.featured-side {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  min-height: 0;
}
.featured-side > * {
  flex: 1 1 0;
  min-height: 0;
}

/* 热门微展位 */
.hotmb-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); }
.hotmb-card {
  padding: var(--space-4);
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: box-shadow 0.18s ease;
}
.hotmb-card:hover { box-shadow: var(--shadow-hover); }
.hotmb-tier { font-size: var(--font-xs); }
/* 头像 + 名称一行：avatar 固定宽高，文字块可收缩 */
.hotmb-top { display: flex; align-items: center; gap: var(--space-2); min-width: 0; }
.hotmb-main { min-width: 0; display: flex; flex-direction: column; }
.hotmb-card strong {
  display: block;
  margin: var(--space-1) 0;
  font-size: var(--font-sm);
  color: var(--ink-900);
}
.hotmb-main strong {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hotmb-stats {
  display: flex;
  gap: var(--space-2);
  font-size: var(--font-xs);
  color: var(--ink-500);
}

/* 热门展会三列 */
.card-grid-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); }

/* 转化区：深蓝卡片 + 金色按钮 */
.convert {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-7);
}
.convert-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-6);
  border-radius: var(--radius-card);
  color: var(--surface-0);
  background: linear-gradient(155deg, var(--brand-900) 0%, var(--brand-800) 100%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: var(--shadow-card);
}
.convert-kicker {
  font-size: var(--font-xs);
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--accent-400);
}
.convert-title {
  font-size: var(--font-h3);
  line-height: var(--line-h3);
  font-weight: var(--weight-h2);
  color: var(--surface-0);
}
.convert-sub {
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: rgba(255, 255, 255, 0.72);
}
.convert-meta {
  font-size: var(--font-xs);
  color: rgba(255, 255, 255, 0.52);
  font-variant-numeric: tabular-nums;
}
.convert-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: var(--space-3);
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-btn);
  font-size: var(--font-sm);
  font-weight: 700;
  color: var(--brand-950);
  background: var(--accent-500);
  transition: background 0.18s ease;
}
.convert-btn:hover { background: var(--accent-400); color: var(--brand-950); }

/* AI 实验室入口（登录可见） */
.ai-lab-entry {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-btn);
  background: var(--surface-1);
  border: 1px solid var(--ink-100);
  color: var(--ink-700);
  transition: border-color 0.15s ease;
}
.ai-lab-entry:hover { border-color: var(--brand-300); color: var(--ink-700); }
.ai-lab-icon { font-size: var(--font-body); }
.ai-lab-text { flex: 1; font-size: var(--font-sm); color: var(--ink-500); }
.ai-lab-text strong { color: var(--ink-900); margin-right: var(--space-1); }
.ai-lab-go { color: var(--accent-700); font-size: var(--font-body); }

@media (max-width: 1024px) {
  .card-grid-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .featured-grid { grid-template-columns: minmax(0, 1fr); }
  .featured-side { flex-direction: row; }
  .featured-side > * { flex: 1 1 0; }
}

@media (max-width: 768px) {
  .hotmb-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .convert { grid-template-columns: minmax(0, 1fr); }
  .convert-card { padding: var(--space-5); }
  .featured-side { flex-direction: column; }
}

@media (max-width: 640px) {
  .home-body { padding: var(--space-5) var(--space-4) var(--space-7); }
  .card-grid-3 { grid-template-columns: minmax(0, 1fr); }
  .hotmb-row { grid-template-columns: minmax(0, 1fr); }
  .convert-btn { align-self: stretch; }
}
</style>
