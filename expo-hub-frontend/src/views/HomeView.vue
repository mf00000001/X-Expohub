<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import HeroBanner from '@/components/HeroBanner.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import CategoryGrid from '@/components/CategoryGrid.vue'
import ActivityFeed from '@/components/ActivityFeed.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import http from '@/api/index'
import { useUserStore } from '@/stores/user'

function tierIcon(t?: string) {
  return ({ free: '🆓', regular: '⭐', flagship: '👑' } as Record<string, string>)[t || 'free'] || '🆓'
}

const userStore = useUserStore()

const router = useRouter()
const featured = ref<Exhibition[]>([])
const hot = ref<Exhibition[]>([])
const upcoming = ref<Exhibition[]>([])
const hotMB = ref<any[]>([])
const loading = ref(true)
const searchKeyword = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const [f, h, u, mb] = await Promise.all([
      exhibitionApi.getFeatured(5),
      exhibitionApi.getHot(10),
      exhibitionApi.getUpcoming(6),
      http.get('/micro-booths?page_size=6').catch(()=>({list:[]})),
    ])
    featured.value = f || []
    hot.value = h || []
    upcoming.value = u || []
    hotMB.value = (mb as any)?.list || (mb as any)?.data?.list || []
  } catch (e) {
    console.error('Failed to load homepage data:', e)
  } finally {
    loading.value = false
  }
})

function goToExhibition(id: number) {
  router.push({ name: 'exhibition-detail', params: { id } })
}
function goToCategory(cat: string) {
  router.push({ name: 'search', query: { cat: cat } })
}
function goToAll() {
  router.push({ name: 'exhibition-list' })
}
function handleSearch(v: string) {
  if (v.trim()) router.push({ name: 'search', query: { q: v.trim() } })
}
</script>

<template>
  <div class="home-v2">
    <!-- 1. Hero + 轮播 -->
    <HeroBanner :exhibitions="featured" @goto="goToExhibition" />

    <!-- 2. 搜索 + 实时动态 -->
    <div class="home-body">
      <div class="home-main">
        <!-- 搜索栏 -->
        <div class="search-row">
          <SearchBar v-model="searchKeyword" placeholder="搜索展会、展商、展品..." @search="handleSearch" />
        </div>

        <!-- AI 实验室入口（登录可见） -->
        <router-link v-if="userStore.isLoggedIn" to="/ai/lab" class="ai-lab-entry">
          <span class="ai-lab-icon">✨</span>
          <span class="ai-lab-text"><strong>AI 实验室</strong> 文案生成 · 翻译 · 采购匹配建议</span>
          <span class="ai-lab-go">›</span>
        </router-link>

        <!-- V2.9: 双钩子引流 -->
        <div class="dual-cta">
          <div class="cta-card exhibitor-cta" @click="$router.push('/register')">
            <span class="cta-emoji">🏪</span>
            <strong>我是展商，免费试水</strong>
            <p>1000家展商已入驻 · 4847件展品获曝光 · 免费挂3件展品</p>
            <span class="cta-link">免费开通微展位 →</span>
          </div>
          <div class="cta-card buyer-cta" @click="$router.push('/micro-booths')">
            <span class="cta-emoji">🔍</span>
            <strong>我是买家，寻找供应商</strong>
            <p>1000+微展位覆盖18个行业 · 直接收藏 · 预约展会见面</p>
            <span class="cta-link">浏览供应商 →</span>
          </div>
        </div>

        <!-- 热门微展位 -->
        <section class="section" v-if="hotMB.length > 0">
          <div class="section-head"><h2>🔥 热门微展位</h2><span class="section-sub">这些展商正在获得买家关注</span></div>
          <div class="hotmb-row">
            <div v-for="mb in hotMB.slice(0,4)" :key="mb.id" class="hotmb-card" @click="$router.push('/micro-booths/'+mb.id)">
              <span class="hotmb-tier">{{ tierIcon(mb.membership_tier) }}</span>
              <strong>{{ mb.name?.slice(0,20) }}</strong>
              <div class="hotmb-stats"><span>👀{{ mb.view_count }}</span><span>❤️{{ mb.favorite_count }}</span><span>📦{{ mb.product_count }}展品</span></div>
            </div>
          </div>
        </section>

        <!-- 精选展会（重磅来袭） -->
        <section class="section" v-if="featured.length > 0">
          <div class="section-head">
            <h2>🔥 重磅来袭</h2>
            <span class="section-sub">精选优质展会，不容错过</span>
            <button class="btn-link" @click="goToAll">查看全部 →</button>
          </div>
          <div class="card-grid-3">
            <ExpoCard v-for="e in featured.slice(0, 6)" :key="e.id" :exhibition="e" @click="goToExhibition(e.id)" />
          </div>
          <div class="scarcity-row" v-if="featured.length > 0">
            <span class="scarcity-tag">🔥 已有 {{ featured[0].visitor_count || 328 }} 人报名</span>
            <span class="scarcity-tag">⏰ 仅剩 12 个展位</span>
          </div>
        </section>

        <!-- 行业分类 -->
        <section class="section">
          <div class="section-head">
            <h2>🏷️ 按行业找展品</h2>
          </div>
          <CategoryGrid @select="goToCategory" />
        </section>

        <!-- 热门展会 -->
        <section class="section" v-if="hot.length > 0">
          <div class="section-head">
            <h2>📈 热门展会</h2>
            <span class="section-sub">大家都在看</span>
          </div>
          <div class="card-grid-3">
            <ExpoCard v-for="e in hot.slice(0, 6)" :key="e.id" :exhibition="e" @click="goToExhibition(e.id)" />
          </div>
        </section>

        <!-- 即将开幕 -->
        <section class="section" v-if="upcoming.length > 0">
          <div class="section-head">
            <h2>📅 即将开幕</h2>
            <span class="section-sub">提前规划你的行程</span>
          </div>
          <div class="card-grid-3">
            <ExpoCard v-for="e in upcoming" :key="e.id" :exhibition="e" @click="goToExhibition(e.id)" />
          </div>
        </section>

        <!-- 底部数据栏 -->
        <div class="stats-bar">
          <div class="stat-item"><strong>200+</strong><span>优质展会</span></div>
          <div class="stat-item"><strong>5,000+</strong><span>入驻展商</span></div>
          <div class="stat-item"><strong>12,000+</strong><span>展品展示</span></div>
          <div class="stat-item"><strong>100+</strong><span>每日新增采购</span></div>
        </div>
      </div>

      <!-- 侧边栏：实时动态 -->
      <aside class="home-sidebar">
        <ActivityFeed />
      </aside>
    </div>

    <LoadingSkeleton v-if="loading" :lines="6" />
  </div>
</template>

<style scoped>
.home-v2 { background: var(--color-bg-page); min-height: 100vh; }
.home-body {
  max-width: 1200px; margin: 0 auto; padding: 24px;
  display: grid; grid-template-columns: 1fr 320px; gap: 24px;
}
.home-main { min-width: 0; }
.home-sidebar { position: sticky; top: 80px; align-self: start; }

.search-row { margin-bottom: 24px; }

.section { margin-bottom: 40px; }
.section-head {
  display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
}
.section-head h2 { font-size: 20px; font-weight: 700; }
.section-sub { font-size: 13px; color: var(--color-text-secondary); flex: 1; }
.btn-link { background: none; border: none; color: var(--color-primary); font-size: 13px; cursor: pointer; }
.btn-link:hover { text-decoration: underline; }

.card-grid-3 {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
}

.scarcity-row { display: flex; gap: 12px; margin-top: 12px; }
.scarcity-tag {
  display: inline-block; padding: 4px 12px; border-radius: 20px;
  font-size: 12px; font-weight: 600;
  background: #fef3c7; color: #d97706;
}

.stats-bar {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;
  padding: 32px; background: linear-gradient(135deg, #1e293b, #312e81);
  border-radius: 16px; color: #fff; margin-top: 40px;
}
.stat-item { text-align: center; }
.stat-item strong { display: block; font-size: 28px; font-weight: 800; margin-bottom: 4px; }
.stat-item span { font-size: 13px; opacity: 0.7; }

.mb-cta {
  display:flex; align-items:center; justify-content:space-between; gap:16px;
  padding:20px 24px; margin:0 0 24px; border-radius:16px;
  background:linear-gradient(135deg,#fef3c7,#fde68a); cursor:pointer; flex-wrap:wrap;
}
.mb-cta-left { display:flex; align-items:center; gap:12px }
.mb-cta-emoji { font-size:36px }
.mb-cta strong { font-size:16px; color:#92400e }
.mb-cta p { font-size:13px; color:#a16207; margin-top:2px }
.mb-cta-btn { padding:10px 20px; background:linear-gradient(135deg,#f59e0b,#d97706); color:#fff; border:none; border-radius:10px; font-size:14px; font-weight:700; cursor:pointer; white-space:nowrap }
.mb-cta-btn:hover { transform:scale(1.05); transition:transform 0.2s }
.dual-cta { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:24px }
.cta-card { padding:20px; border-radius:14px; cursor:pointer; transition:transform 0.15s }
.cta-card:hover { transform:translateY(-2px) }
.exhibitor-cta { background:linear-gradient(135deg,#fef3c7,#fde68a) }
.buyer-cta { background:linear-gradient(135deg,#dbeafe,#bfdbfe) }
.cta-emoji { font-size:28px; display:block; margin-bottom:8px }
.cta-card strong { font-size:15px; display:block; margin-bottom:4px }
.cta-card p { font-size:12px; color:#64748b; margin-bottom:8px }
.cta-link { font-size:13px; font-weight:600; color:#3b82f6 }
.hotmb-row { display:grid; grid-template-columns:repeat(4,1fr); gap:12px }
.hotmb-card { padding:14px; background:#fff; border-radius:10px; cursor:pointer; box-shadow:0 1px 3px rgba(0,0,0,0.04) }
.hotmb-card:hover { box-shadow:0 4px 12px rgba(0,0,0,0.08) }
.hotmb-tier { font-size:12px }
.hotmb-card strong { display:block; font-size:13px; margin:4px 0 }
.hotmb-stats { display:flex; gap:8px; font-size:11px; color:#64748b; margin-top:4px }
@media(max-width:768px){.dual-cta{grid-template-columns:1fr}.hotmb-row{grid-template-columns:repeat(2,1fr)}}

@media (max-width: 1024px) {
  .home-body { grid-template-columns: 1fr; }
  .home-sidebar { display: none; }
  .card-grid-3 { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .card-grid-3 { grid-template-columns: 1fr; }
  .stats-bar { grid-template-columns: repeat(2, 1fr); gap: 16px; padding: 20px; }
  .stat-item strong { font-size: 22px; }
}

.ai-lab-entry {
  display:flex; align-items:center; gap:10px; margin-bottom:16px;
  padding:10px 14px; border-radius:12px;
  background:linear-gradient(90deg, rgba(99,102,241,.12), rgba(168,85,247,.10));
  border:1px solid rgba(99,102,241,.28); color:var(--foreground);
  text-decoration:none; transition:box-shadow .15s;
}
.ai-lab-entry:hover { box-shadow:0 2px 10px rgba(99,102,241,.18) }
.ai-lab-icon { font-size:18px }
.ai-lab-text { flex:1; font-size:14px; color:var(--muted-foreground) }
.ai-lab-text strong { color:var(--foreground); margin-right:6px }
.ai-lab-go { color:var(--accent); font-size:18px }

</style>
