<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import StatsCard from '@/components/StatsCard.vue'
import { boothApi } from '@/api/booth'
import { productApi } from '@/api/product'
import { procurementApi } from '@/api/procurement'
import { messageApi } from '@/api/message'
import http from '@/api/index'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const myBooths = ref<any[]>([])
const myProducts = ref<any[]>([])
const procurements = ref<any[]>([])
const unreadCount = ref(0)

// 展商信誉等级
const exhibitorTier = ref('')
const tierScore = ref(0)
const tierLabel = ref('')
const tierIcon = ref('⭐')
const tierColor = ref('#6b7280')

// AI推荐
const recommendations = ref<any[]>([])

function toList(res: any): any[] {
  if (Array.isArray(res)) return res
  if (!res) return []
  return res.list || res.items || res.results || res.data || []
}

const boothCount = computed(() => myBooths.value.length)
const productCount = computed(() => myProducts.value.length)
const matchCount = computed(() => {
  return procurements.value.reduce((sum: number, p: any) => {
    const mc = p.match_count ?? p.matchCount ?? 0
    return sum + (typeof mc === 'number' ? mc : 0)
  }, 0)
})

const recentBooths = computed(() => myBooths.value.slice(0, 4))
const recentProducts = computed(() => myProducts.value.slice(0, 4))

function statusClass(status: string): string {
  const s = (status || '').toLowerCase()
  if (['published','active','approved','confirmed','open','occupied','booked'].includes(s)) return 'tag tag-success'
  if (['pending','draft','review'].includes(s)) return 'tag tag-warning'
  if (['cancelled','rejected','closed','available'].includes(s)) return 'tag tag-info'
  return 'tag'
}
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    published:'已发布',active:'进行中',approved:'已通过',confirmed:'已确认',
    pending:'待审核',draft:'草稿',review:'审核中',
    cancelled:'已取消',rejected:'已驳回',closed:'已关闭',
    open:'开放',booked:'已预订',occupied:'已占用',available:'可预订'
  }
  return map[(status || '').toLowerCase()] || status || '未知'
}
function formatDate(d: string): string {
  if (!d) return '-'
  return new Date(d).toLocaleDateString('zh-CN')
}

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const [boothRes, prodRes, procRes, msgRes, tierRes, recRes] = await Promise.all([
      boothApi.getMyBooths().catch(() => []),
      productApi.getMyProducts().catch(() => []),
      procurementApi.getList({ page_size: 100 }).catch(() => []),
      messageApi.getUnreadCount().catch(() => ({ unread_count: 0 })),
      http.get('/growth/tier').catch(() => ({})),
      http.get('/recommendations/for-exhibitor').catch(() => ({})),
    ])
    myBooths.value = toList(boothRes)
    myProducts.value = toList(prodRes)
    procurements.value = toList(procRes)
    unreadCount.value = (msgRes as any)?.unread_count ?? (msgRes as any)?.unreadCount ?? 0
    const td = (tierRes as any)?.data || tierRes
    if (td?.tier) {
      exhibitorTier.value = td.tier
      tierScore.value = td.score || 0
      tierLabel.value = td.label || ''
      const colors: Record<string, string> = { bronze: '#a16207', silver: '#6b7280', gold: '#f59e0b', diamond: '#6366f1' }
      tierColor.value = colors[td.tier] || '#6b7280'
      const icons: Record<string, string> = { bronze: '🥉', silver: '🥈', gold: '🥇', diamond: '💎' }
      tierIcon.value = icons[td.tier] || '⭐'
    }
    const rdata = (recRes as any)?.data || recRes
    recommendations.value = Array.isArray(rdata) ? rdata : (rdata?.list || [])
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.response?.data?.message || e.message || '加载仪表盘数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="dashboard">
        <main class="main-content">
      <div class="container">
        <header class="page-header">
          <h1 class="page-title">展商工作台</h1>
          <p class="page-subtitle">展位、展品与采购匹配概览</p>
        </header>

        <!-- Loading skeleton -->
        <template v-if="loading">
          <div class="stats-grid">
            <div v-for="i in 4" :key="i" class="card skeleton-card">
              <div class="skeleton skeleton-icon"></div>
              <div class="skeleton skeleton-text skeleton-text-short"></div>
              <div class="skeleton skeleton-text skeleton-text-long"></div>
            </div>
          </div>
          <div class="skeleton-grid">
            <div v-for="i in 2" :key="i" class="card skeleton-block"></div>
          </div>
        </template>

        <!-- Error -->
        <div v-else-if="error" class="card error-card">
          <div class="error-icon">!</div>
          <p class="error-msg">{{ error }}</p>
          <button class="btn btn-primary" @click="fetchData">重新加载</button>
        </div>

        <!-- Content -->
        <template v-else>
          <!-- V2.4: 新手引导 -->
          <div class="card newbie-guide" v-if="productCount === 0 && boothCount === 0">
            <h3>👋 欢迎！3步开启你的第一笔商机</h3>
            <div class="newbie-steps">
              <div class="newbie-step done"><span class="ns-num">1</span><span>完善企业资料</span><span class="ns-arrow">→</span></div>
              <div class="newbie-step"><span class="ns-num">2</span><span>创建微展位</span><span class="ns-arrow">→</span></div>
              <div class="newbie-step"><span class="ns-num">3</span><span>上传展品获客</span></div>
            </div>
            <button class="btn btn-primary" @click="router.push('/exhibitor/micro-booth')" style="margin-top:12px">开始 → 创建免费微展位</button>
          </div>

          <!-- KPI stat row -->
          <div class="stats-grid">
            <StatsCard icon="&#x1f3e2;" label="我的展位" :value="boothCount" color="#3B82F6" to="/exhibitor/booths" />
            <StatsCard icon="&#x1f4e6;" label="我的展品" :value="productCount" color="#10B981" to="/exhibitor/products" />
            <StatsCard icon="&#x1f91d;" label="采购匹配数" :value="matchCount" color="#6366F1" to="/exhibitor/matches" />
            <StatsCard icon="&#x1f4ec;" label="未读消息" :value="unreadCount" color="#F59E0B" to="/messages" />
            <StatsCard v-if="exhibitorTier" :icon="tierIcon" :label="tierLabel" :value="tierScore" :color="tierColor" />
          </div>

          <div class="dashboard-grid">
            <!-- My booths -->
            <div class="card">
              <div class="card-title-row">
                <h3 class="card-title">我的展位</h3>
                <button class="btn btn-sm btn-outline" @click="router.push('/exhibitor/booths')">
                  管理展位 &rarr;
                </button>
              </div>
              <div v-if="recentBooths.length === 0" class="empty-state">
                暂无展位，<a href="#" @click.prevent="router.push('/exhibitor/booths')">去申请展位</a>
              </div>
              <ul v-else class="item-list">
                <li v-for="booth in recentBooths" :key="booth.id" class="item-row">
                  <div class="item-icon">&#x1f3e2;</div>
                  <div class="item-info">
                    <span class="item-name">
                      {{ booth.name || booth.booth_number || booth.boothNumber || '展位 #' + booth.id }}
                    </span>
                    <span class="item-meta">
                      展会: {{ booth.exhibition?.name || booth.exhibitionName || '未知' }}
                      &middot; {{ booth.area || booth.area_sqm ? (booth.area || booth.area_sqm) + 'm²' : '' }}
                    </span>
                  </div>
                  <span :class="statusClass(booth.status)">{{ statusLabel(booth.status) }}</span>
                </li>
              </ul>
            </div>

            <!-- My products -->
            <div class="card">
              <div class="card-title-row">
                <h3 class="card-title">我的展品</h3>
                <button class="btn btn-sm btn-outline" @click="router.push('/exhibitor/products')">
                  管理展品 &rarr;
                </button>
              </div>
              <div v-if="recentProducts.length === 0" class="empty-state">
                暂无展品，<a href="#" @click.prevent="router.push('/exhibitor/products/create')">添加展品</a>
              </div>
              <ul v-else class="item-list">
                <li v-for="prod in recentProducts" :key="prod.id" class="item-row">
                  <div class="item-icon">&#x1f4e6;</div>
                  <div class="item-info">
                    <span class="item-name">{{ prod.name || '展品 #' + prod.id }}</span>
                    <span class="item-meta">
                      {{ prod.category || '未分类' }}
                      <template v-if="prod.price !== undefined && prod.price !== null">
                        &middot; &yen;{{ typeof prod.price === 'number' ? prod.price.toLocaleString() : prod.price }}
                      </template>
                    </span>
                  </div>
                  <span :class="statusClass(prod.status)">{{ statusLabel(prod.status) }}</span>
                </li>
              </ul>
            </div>
          </div>

          <!-- Procurement matches alert -->
          <div class="card matches-card" v-if="matchCount > 0">
            <div class="card-title-row">
              <h3 class="card-title">采购匹配提醒</h3>
              <button class="btn btn-sm btn-outline" @click="router.push('/exhibitor/matches')">
                查看全部 &rarr;
              </button>
            </div>
            <div class="matches-alert">
              <span class="matches-badge">{{ matchCount }}</span>
              <span>个采购需求与您的展品可能匹配，点击查看详情</span>
            </div>
          </div>

          <!-- AI推荐 -->
          <div class="card" v-if="recommendations.length > 0" style="margin-bottom:20px">
            <h3 style="margin-bottom:12px">🤖 智能匹配推荐</h3>
            <p style="font-size:12px;color:var(--color-text-secondary);margin-bottom:12px">根据你的行业领域，为你找到以下采购需求：</p>
            <div class="rec-list">
              <div class="rec-item" v-for="r in recommendations.slice(0,3)" :key="r.id">
                <div class="rec-info">
                  <strong>{{ r.title }}</strong>
                  <span style="font-size:12px;color:var(--color-text-secondary)">{{ r.category }} · {{ r.reasons?.join('，') }}</span>
                </div>
                <router-link :to="'/procurements/'+r.id" class="btn btn-sm btn-primary-outline">查看详情</router-link>
              </div>
            </div>
          </div>

          <!-- Quick actions -->
          <div class="card quick-actions">
            <h3 class="card-title">快捷操作</h3>
            <div class="actions-grid">
              <button class="action-btn" @click="router.push('/exhibitor/products/create')">
                <span class="action-icon">&#x2795;</span>
                <span class="action-label">添加展品</span>
              </button>
              <button class="action-btn" @click="router.push('/exhibitor/booths')">
                <span class="action-icon">&#x1f3e2;</span>
                <span class="action-label">我的展位</span>
              </button>
              <button class="action-btn" @click="router.push('/exhibitor/products')">
                <span class="action-icon">&#x1f4e6;</span>
                <span class="action-label">我的展品</span>
              </button>
              <button class="action-btn" @click="router.push('/exhibitor/micro-booth')">
                <span class="action-icon">🏪</span>
                <span class="action-label">微展位</span>
              </button>
              <button class="action-btn" @click="router.push('/exhibitor/poster')">
                <span class="action-icon">📸</span>
                <span class="action-label">名片海报</span>
              </button>
              <button class="action-btn" @click="router.push('/exhibitor/matches')">
                <span class="action-icon">&#x1f91d;</span>
                <span class="action-label">采购匹配</span>
              </button>
            </div>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
.rec-list { display: flex; flex-direction: column; gap: 8px; }
.rec-item { display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--color-bg-page); border-radius: 8px; }
.rec-info { flex: 1; }
.rec-info strong { display: block; font-size: 14px; margin-bottom: 2px; }

.newbie-guide { background:linear-gradient(135deg,#eff6ff,#dbeafe); margin-bottom:20px }
.newbie-guide h3 { font-size:16px; margin-bottom:12px }
.newbie-steps { display:flex; gap:8px; align-items:center; flex-wrap:wrap }
.newbie-step { display:flex; align-items:center; gap:6px; font-size:13px; color:#64748b }
.newbie-step.done { color:#10b981 }
.ns-num { width:22px;height:22px;border-radius:50%;background:#e2e8f0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700 }
.newbie-step.done .ns-num { background:#10b981;color:#fff }
.ns-arrow { color:#94a3b8;margin:0 2px }
.dashboard {
  min-height: 100vh;
  background: var(--bg-color);
}
.main-content {
  padding-top: calc(var(--header-height) + var(--spacing-lg));
  padding-bottom: var(--spacing-xl);
}

/* Header */
.page-header {
  margin-bottom: var(--spacing-lg);
}
.page-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}
.page-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 4px;
}

/* Stat grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

/* Dashboard 2-col layout */
.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

/* Card headings */
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-md) 0;
}
.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}
.card-title-row .card-title {
  margin-bottom: 0;
}

/* Item list */
.item-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}
.item-row:last-child {
  border-bottom: none;
}
.item-icon {
  font-size: 22px;
  flex-shrink: 0;
  width: 32px;
  text-align: center;
}
.item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.item-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

/* Matches alert */
.matches-card {
  margin-bottom: var(--spacing-lg);
}
.matches-alert {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: #EEF2FF;
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--text-primary);
}
.matches-badge {
  background: var(--info);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

/* Quick actions */
.quick-actions {
  margin-bottom: var(--spacing-lg);
}
.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--spacing-sm);
}
.action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-white);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 14px;
  color: var(--text-primary);
}
.action-btn:hover {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--primary);
}
.action-icon {
  font-size: 18px;
}
.action-label {
  font-weight: 500;
}

/* Skeleton loading */
.skeleton-card {
  padding: var(--spacing-md);
}
.skeleton {
  background: linear-gradient(90deg, #e5e7eb 25%, #f3f4f6 50%, #e5e7eb 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
}
.skeleton-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  margin-bottom: 8px;
}
.skeleton-text {
  height: 14px;
  margin-bottom: 6px;
}
.skeleton-text-short { width: 60%; }
.skeleton-text-long { width: 80%; }
.skeleton-block {
  height: 200px;
}
.skeleton-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Empty & error */
.empty-state {
  text-align: center;
  color: var(--text-secondary);
  font-size: 14px;
  padding: 32px 16px;
}
.empty-state a {
  color: var(--primary);
  text-decoration: underline;
}
.error-card {
  text-align: center;
  padding: 40px var(--spacing-lg);
}
.error-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #FEF2F2;
  color: var(--danger);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 12px;
}
.error-msg {
  color: var(--text-secondary);
  margin-bottom: 16px;
}

/* Responsive */
@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .dashboard-grid,
  .skeleton-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
