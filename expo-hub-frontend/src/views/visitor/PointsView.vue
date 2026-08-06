<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/index'
import { pointsApi } from '@/api/points'
import { isLoggedIn } from '@/utils/auth'

const router = useRouter()
const loggedIn = isLoggedIn()
function requireLogin(action: string): boolean {
  if (!isLoggedIn()) { alert(`请先登录后再${action}`); router.push('/login'); return false }
  return true
}
const balance = ref(0)
const todayEarned = ref(0)
const dailyStats = ref<any>({})
const history = ref<any[]>([])
const catalog = ref<any[]>([])
const loading = ref(true)

// 签到
const checkedInToday = ref(false)
const checkinStreak = ref(0)
const checking = ref(false)

// 邀请
const referralCode = ref('')
const invitedCount = ref(0)
const inviteCode = ref('')
const inviting = ref(false)

// 任务列表（模仿淘宝外卖的任务卡片）
const tasks = ref([
  { key: 'earn_browse', label: '👀 浏览展商', desc: '看看有哪些优质展商', points: 1, cap: 10, action: '/exhibitions', btn: '去浏览' },
  { key: 'earn_procurement', label: '📦 发布采购需求', desc: '告诉展商你要什么', points: 5, cap: 25, action: '/visitor/procurements/create', btn: '去发布' },
  { key: 'earn_booking', label: '📅 预约展位', desc: '提前锁定心仪展位', points: 10, cap: 30, action: '/exhibitions', btn: '去预约' },
  { key: 'earn_registration', label: '🎫 报名展会', desc: '报名参加感兴趣的展会', points: 15, cap: 30, action: '/exhibitions', btn: '去报名' },
])

onMounted(async () => {
  if (!isLoggedIn()) { loading.value = false; return }
  try {
    const [b, ds, h, c] = await Promise.all([
      pointsApi.balance(), pointsApi.dailyStats(),
      pointsApi.history({ page_size: 10 }), pointsApi.catalog(),
    ])
    balance.value = (b as any)?.balance || 0
    todayEarned.value = (b as any)?.today_earned || 0
    dailyStats.value = ds || {}
    history.value = (h as any)?.list || []
    catalog.value = (c as any) || []

    // 签到状态
    const cs: any = await http.get('/growth/checkin/status').catch(() => ({}))
    checkedInToday.value = cs?.checked_in_today ?? false
    checkinStreak.value = cs?.streak ?? 0

    // 邀请信息
    const ref: any = await http.get('/growth/referral/my-code').catch(() => ({}))
    referralCode.value = ref?.referral_code || ''
    invitedCount.value = ref?.invited_count || 0
  } catch (e) { console.error(e) } finally { loading.value = false }

  // sync task progress
  for (const t of tasks.value) {
    const stat = (dailyStats.value as any)?.[t.key]
    if (stat) {
      (t as any).earned = stat.today_earned || 0
      ;(t as any).remaining = stat.remaining || 0
      ;(t as any).done = (stat.today_earned || 0) >= (stat.daily_cap || t.cap)
    }
  }
})

async function handleCheckin() {
  if (!requireLogin('签到')) return
  checking.value = true
  try {
    const res: any = await http.post('/growth/checkin')
    alert(res?.message || '签到成功')
    checkedInToday.value = true
    checkinStreak.value = res?.streak || checkinStreak.value + 1
    balance.value = res?.balance || balance.value
  } catch (e: any) { alert(e?.response?.data?.message || '签到失败') }
  finally { checking.value = false }
}

async function handleApplyReferral() {
  if (!requireLogin('使用邀请码')) return
  if (!inviteCode.value) return
  inviting.value = true
  try {
    const res: any = await http.post('/growth/referral/apply', { referral_code: inviteCode.value })
    alert(res?.message || '邀请成功')
    balance.value += 100
    inviteCode.value = ''
  } catch (e: any) { alert(e?.response?.data?.message || '邀请失败') }
  finally { inviting.value = false }
}

function copyCode() {
  navigator.clipboard?.writeText(referralCode.value)
  alert('邀请码已复制！')
}

function goTask(path: string) {
  if (path.includes('create') && !requireLogin('发布采购需求')) return
  router.push(path)
}
function goRedeem() { window.scrollTo({ top: 600, behavior: 'smooth' }) }
</script>

<template>
  <div class="points-v2">
    <!-- 积分余额头部 -->
    <div class="header-card">
      <div class="header-left">
        <div class="coin-icon">🪙</div>
        <div>
          <div class="coin-balance">{{ balance }}</div>
          <div class="coin-sub">今日获得 +{{ todayEarned }}</div>
        </div>
      </div>
      <div class="header-right">
        <div class="streak-badge" :class="{ active: checkedInToday }">
          🔥 连续{{ checkinStreak }}天
        </div>
        <button class="checkin-btn" :disabled="checkedInToday || checking" @click="handleCheckin">
          {{ checkedInToday ? '✅ 已签到' : '签到+2' }}
        </button>
      </div>
    </div>

    <!-- 赚积分任务 -->
    <div class="section">
      <div class="section-hd"><h3>🎯 赚积分</h3><span class="section-sub">完成任务领积分，每日上限自动刷新</span></div>
      <div class="task-list">
        <div v-for="t in tasks" :key="t.key" class="task-card" :class="{ done: (t as any).done }" @click="goTask(t.action)">
          <div class="task-left">
            <span class="task-icon">{{ t.label.slice(0, 2) }}</span>
            <div>
              <div class="task-label">{{ t.label.slice(2) }}</div>
              <div class="task-desc">{{ t.desc }} · 每次+{{ t.points }}分</div>
            </div>
          </div>
          <div class="task-right">
            <div class="task-progress-text" v-if="!((t as any).done)">今日{{ (t as any).earned || 0 }}/{{ t.cap }}</div>
            <span class="task-btn" :class="{ full: (t as any).done }" @click.stop="goTask(t.action)">
              {{ (t as any).done ? '今日已满' : t.btn }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 兑换商城 -->
    <div class="section" v-if="catalog.length > 0">
      <div class="section-hd"><h3>🎁 积分兑换</h3></div>
      <div class="redeem-row">
        <div v-for="item in catalog" :key="(item as any).id" class="redeem-card">
          <div class="rc-icon">{{ (item as any).icon }}</div>
          <div class="rc-name">{{ (item as any).name }}</div>
          <div class="rc-cost">{{ (item as any).points }}积分</div>
          <button class="btn btn-sm btn-primary" :disabled="balance < (item as any).points" @click="async () => { try { await pointsApi.redeem((item as any).id); alert('兑换成功！'); const b: any = await pointsApi.balance(); balance = b?.balance || 0 } catch(e: any) { alert(e?.response?.data?.message||'失败') } }">
            {{ balance < (item as any).points ? '积分不足' : '兑换' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 邀请好友 -->
    <div class="section">
      <div class="section-hd"><h3>👥 邀请好友</h3><span class="section-sub">每邀请1人，双方各得100积分</span></div>
      <div class="invite-card">
        <div class="invite-code-box" @click="copyCode">
          <span>你的邀请码</span>
          <strong>{{ referralCode }}</strong>
          <span style="font-size:11px;color:var(--color-primary)">点击复制</span>
        </div>
        <div style="text-align:center;font-size:13px;color:var(--color-text-secondary);margin-top:8px">已邀请 {{ invitedCount }} 人</div>
        <div class="invite-input-row">
          <input v-model="inviteCode" class="form-input" placeholder="输入朋友的邀请码" />
          <button class="btn btn-sm btn-primary" :disabled="inviting" @click="handleApplyReferral">使用</button>
        </div>
      </div>
    </div>

    <!-- 积分明细 -->
    <div class="section" v-if="history.length > 0">
      <div class="section-hd"><h3>📜 积分明细</h3></div>
      <div class="history-list">
        <div v-for="h in history" :key="(h as any).id" class="hitem">
          <span :style="{color: (h as any).amount > 0 ? '#10b981' : '#ef4444'}">{{ (h as any).amount > 0 ? '+' : '' }}{{ (h as any).amount }}</span>
          <span style="flex:1">{{ (h as any).description }}</span>
          <span class="text-muted">{{ (h as any).created_at?.slice(0,10) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.points-v2 { max-width: 600px; margin: 0 auto; padding-bottom: 40px; }
.header-card { display: flex; justify-content: space-between; align-items: center;
  padding: 24px; background: linear-gradient(135deg, #f59e0b 0%, #ef4444 60%, #dc2626 100%);
  border-radius: 16px; color: #fff; margin-bottom: 24px; }
.header-left { display: flex; align-items: center; gap: 12px; }
.coin-icon { font-size: 36px; }
.coin-balance { font-size: 36px; font-weight: 800; line-height: 1; }
.coin-sub { font-size: 12px; opacity: 0.8; margin-top: 4px; }
.header-right { text-align: right; }
.streak-badge { font-size: 12px; padding: 2px 10px; border-radius: 10px; background: rgba(255,255,255,0.2); display: inline-block; margin-bottom: 6px; }
.streak-badge.active { background: rgba(255,255,255,0.3); }
.checkin-btn { padding: 6px 16px; border-radius: 20px; border: 2px solid rgba(255,255,255,0.5); background: transparent; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; }
.checkin-btn:disabled { opacity: 0.5; cursor: default; }
.section { margin-bottom: 24px; }
.section-hd { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; }
.section-hd h3 { font-size: 17px; font-weight: 700; }
.section-sub { font-size: 12px; color: var(--color-text-secondary); }
.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-card { display: flex; justify-content: space-between; align-items: center;
  padding: 14px 16px; background: var(--color-bg-card); border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04); cursor: pointer; transition: transform 0.15s; }
.task-card:hover { transform: translateY(-1px); }
.task-card.done { opacity: 0.6; }
.task-left { display: flex; align-items: center; gap: 12px; }
.task-label { font-size: 15px; font-weight: 600; margin-bottom: 2px; }
.task-desc { font-size: 12px; color: var(--color-text-secondary); }
.task-right { text-align: right; }
.task-progress-text { font-size: 11px; color: var(--color-text-secondary); margin-bottom: 4px; }
.task-btn { padding: 4px 14px; border-radius: 16px; border: none; background: var(--color-primary); color: #fff; font-size: 12px; font-weight: 500; cursor: pointer; display: inline-block; }
.task-btn.full { background: #e5e7eb; color: #9ca3af; }
.redeem-row { display: flex; gap: 12px; overflow-x: auto; padding: 4px 0; }
.redeem-card { flex: 0 0 160px; padding: 16px; background: var(--color-bg-card); border-radius: 12px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
.rc-icon { font-size: 32px; margin-bottom: 8px; }
.rc-name { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.rc-cost { font-size: 12px; color: var(--color-text-secondary); margin-bottom: 10px; }
.invite-card { padding: 16px; background: var(--color-bg-card); border-radius: 12px; }
.invite-code-box { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 16px; background: var(--color-bg-page); border-radius: 12px; cursor: pointer; }
.invite-code-box strong { font-size: 22px; letter-spacing: 2px; color: var(--color-primary); }
.invite-input-row { display: flex; gap: 8px; margin-top: 12px; }
.invite-input-row input { flex: 1; }
.history-list { display: flex; flex-direction: column; gap: 6px; }
.hitem { display: flex; align-items: center; gap: 10px; font-size: 13px; padding: 6px 0; border-bottom: 1px solid var(--color-border-lighter); }
</style>
