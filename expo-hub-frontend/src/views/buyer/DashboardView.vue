<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import StatsCard from '@/components/StatsCard.vue'
import { procurementApi } from '@/api/procurement'
import { registrationApi } from '@/api/registration'
import { messageApi } from '@/api/message'
import http from '@/api/index'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const myProcurements = ref<any[]>([])
const myRegistrations = ref<any[]>([])
const unreadCount = ref(0)
const buyerRecs = ref<any[]>([])

function toList(res: any): any[] {
  if (Array.isArray(res)) return res
  if (!res) return []
  return res.list || res.items || res.results || res.data || []
}

const procurementCount = computed(() => myProcurements.value.length)

const matchedCount = computed(() => {
  return myProcurements.value.reduce((sum: number, p: any) => {
    const mc = p.match_count ?? p.matchCount ?? 0
    return sum + (typeof mc === 'number' ? mc : 0)
  }, 0)
})

const registrationCount = computed(() => myRegistrations.value.length)

const recentProcurements = computed(() => myProcurements.value.slice(0, 5))
const recentRegistrations = computed(() => myRegistrations.value.slice(0, 5))

function statusClass(status: string): string {
  const s = (status || '').toLowerCase()
  if (['active','open','published','approved','confirmed'].includes(s)) return 'tag tag-success'
  if (['pending','draft','review'].includes(s)) return 'tag tag-warning'
  if (['cancelled','closed','rejected','fulfilled','matched'].includes(s)) return 'tag tag-info'
  return 'tag'
}
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    active:'进行中',open:'开放中',published:'已发布',approved:'已通过',confirmed:'已确认',
    pending:'待审核',draft:'草稿',review:'审核中',
    cancelled:'已取消',closed:'已关闭',rejected:'已驳回',
    fulfilled:'已满足',matched:'已匹配'
  }
  return map[(status || '').toLowerCase()] || status || '未知'
}
function formatDate(d: string): string {
  if (!d) return '-'
  return new Date(d).toLocaleDateString('zh-CN')
}
function budgetText(p: any): string {
  const min = p.budget_min ?? p.budgetMin
  const max = p.budget_max ?? p.budgetMax
  if (min && max) return '¥' + Number(min).toLocaleString() + ' - ¥' + Number(max).toLocaleString()
  if (min) return '¥' + Number(min).toLocaleString() + ' 起'
  if (max) return '≤ ¥' + Number(max).toLocaleString()
  return '预算未指定'
}
function exhibitionName(reg: any): string {
  return reg.exhibition?.name || reg.exhibitionName || reg.exhibition_title || reg.exhibitionTitle || '未知展会'
}

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const [procRes, regRes, msgRes, recRes] = await Promise.all([
      procurementApi.getMyProcurements().catch(() => []),
      registrationApi.getMyRegistrations().catch(() => []),
      messageApi.getUnreadCount().catch(() => ({ unread_count: 0 })),
      http.get('/recommendations/for-buyer').catch(() => ({})),
    ])
    myProcurements.value = toList(procRes)
    myRegistrations.value = toList(regRes)
    unreadCount.value = (msgRes as any)?.unread_count ?? (msgRes as any)?.unreadCount ?? 0
    const rd = (recRes as any)?.data || recRes
    buyerRecs.value = Array.isArray(rd) ? rd : []
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
          <h1 class="page-title">买家工作台</h1>
          <p class="page-subtitle">采购需求与展会报名概览</p>
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
          <!-- KPI stat row -->
          <div class="stats-grid">
            <StatsCard icon="&#x1f4cb;" label="我的采购需求" :value="procurementCount" color="#3B82F6" />
            <StatsCard icon="&#x1f91d;" label="已匹配数" :value="matchedCount" color="#10B981" />
            <StatsCard icon="&#x1f3aa;" label="已报名展会" :value="registrationCount" color="#6366F1" />
            <StatsCard icon="&#x1f4ec;" label="未读消息" :value="unreadCount" color="#F59E0B" />
          </div>

          <div class="dashboard-grid">
            <!-- My procurements -->
            <div class="card">
              <div class="card-title-row">
                <h3 class="card-title">我的采购需求</h3>
                <button class="btn btn-sm btn-outline" @click="router.push('/buyer/procurements')">
                  查看全部 &rarr;
                </button>
              </div>
              <div v-if="recentProcurements.length === 0" class="empty-state">
                暂无采购需求，<a href="#" @click.prevent="router.push('/buyer/procurements/create')">立即发布</a>
              </div>
              <ul v-else class="item-list">
                <li v-for="proc in recentProcurements" :key="proc.id" class="item-row">
                  <div class="item-icon">&#x1f4cb;</div>
                  <div class="item-info">
                    <span class="item-name">{{ proc.title || '采购 #' + proc.id }}</span>
                    <span class="item-meta">
                      {{ proc.category || '未分类' }} &middot; {{ budgetText(proc) }}
                    </span>
                  </div>
                  <div class="item-right">
                    <span :class="statusClass(proc.status)">{{ statusLabel(proc.status) }}</span>
                    <span v-if="(proc.match_count ?? proc.matchCount) > 0" class="match-count">
                      {{ proc.match_count ?? proc.matchCount }} 匹配
                    </span>
                  </div>
                </li>
              </ul>
            </div>

            <!-- My registered exhibitions -->
            <div class="card">
              <div class="card-title-row">
                <h3 class="card-title">已报名展会</h3>
                <button class="btn btn-sm btn-outline" @click="router.push('/buyer/registrations')">
                  查看全部 &rarr;
                </button>
              </div>
              <div v-if="recentRegistrations.length === 0" class="empty-state">
                暂无报名记录，<a href="#" @click.prevent="router.push('/exhibitions')">浏览展会</a>
              </div>
              <ul v-else class="item-list">
                <li v-for="reg in recentRegistrations" :key="reg.id" class="item-row">
                  <div class="item-icon">&#x1f3aa;</div>
                  <div class="item-info">
                    <span class="item-name">{{ exhibitionName(reg) }}</span>
                    <span class="item-meta">
                      报名时间: {{ formatDate(reg.created_at || reg.createdAt) }}
                    </span>
                  </div>
                  <span :class="statusClass(reg.status || 'confirmed')">
                    {{ reg.ticket_code || reg.ticketCode ? '已出票' : '已报名' }}
                  </span>
                </li>
              </ul>
            </div>
          </div>

          <!-- AI推荐 -->
          <div class="card" v-if="buyerRecs.length > 0" style="margin-bottom:20px">
            <h3 style="margin-bottom:8px">🤖 为你推荐展品</h3>
            <div class="rec-list">
              <div v-for="r in buyerRecs.slice(0,5)" :key="r.id" class="rec-item" @click="router.push('/products/'+r.id)" style="cursor:pointer">
                <span class="rec-name">{{ r.name }}</span>
                <span class="rec-cat">{{ r.category }}</span>
                <span class="rec-reason">{{ r.reasons?.[0] || '' }}</span>
              </div>
            </div>
          </div>

          <!-- Quick actions -->
          <div class="card quick-actions">
            <h3 class="card-title">快捷操作</h3>
            <div class="actions-grid">
              <button class="action-btn action-btn-primary" @click="router.push('/buyer/procurements/create')">
                <span class="action-icon">&#x2795;</span>
                <span class="action-label">发布采购需求</span>
              </button>
              <button class="action-btn" @click="router.push('/exhibitions')">
                <span class="action-icon">&#x1f3aa;</span>
                <span class="action-label">浏览展会</span>
              </button>
              <button class="action-btn" @click="router.push('/buyer/procurements')">
                <span class="action-icon">&#x1f4cb;</span>
                <span class="action-label">采购管理</span>
              </button>
              <button class="action-btn" @click="router.push('/buyer/registrations')">
                <span class="action-icon">&#x2705;</span>
                <span class="action-label">我的报名</span>
              </button>
            </div>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>

<style scoped>
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
.item-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}
.match-count {
  font-size: 11px;
  color: var(--info);
  font-weight: 600;
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
.action-btn-primary {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}
.action-btn-primary:hover {
  background: var(--primary-dark);
  color: #fff;
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
