<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/stores/user'
import StatsCard from '@/components/StatsCard.vue'
import { registrationApi } from '@/api/registration'
import { procurementApi } from '@/api/procurement'
import { messageApi } from '@/api/message'
import { dashboardApi } from '@/api/dashboard'

const userStore = useUserStore()

const roleMap: Record<string, string> = {
  visitor: '游客',
  buyer: '采购商',
  exhibitor: '展商',
  organizer: '主办方',
}

const roleLabel = computed(() => {
  const role = userStore.profile?.role || ''
  return roleMap[role] || role
})

const roleTagCls = computed(() => {
  const role = userStore.profile?.role || ''
  if (role === 'exhibitor') return 'tag-blue'
  if (role === 'organizer') return 'tag-yellow'
  if (role === 'buyer') return 'tag-green'
  return 'tag-gray'
})

const displayName = computed(() => userStore.profile?.nickname || userStore.profile?.username || '')

const totalPoints = computed<number | null>(() => {
  const v = userStore.profile?.total_points
  return typeof v === 'number' ? v : null
})

const role = computed(() => userStore.profile?.role || '')
const isExhibitor = computed(() => role.value === 'exhibitor')
const isOrganizer = computed(() => role.value === 'organizer')

onShow(async () => {
  // 已登录才拉取资料+统计；未登录展示「点击登录」入口
  if (userStore.isLoggedIn) {
    try {
      await userStore.fetchProfile()
    } catch (err) {
      // token 失效交给请求层 401 逻辑处理
    }
    loadStats()
  }
})

// 顶部数字卡片统计（按角色取不同数据源）
const stats = ref({ registrations: 0, procurements: 0, unread: 0 })
const exStats = ref({ booths: 0, products: 0, matches: 0 })
const orgStats = ref({ exhibitions: 0, booths: 0, users: 0 })

async function loadStats() {
  if (!userStore.isLoggedIn) return
  try {
    if (isExhibitor.value) {
      const ov = await dashboardApi.getExhibitorOverview()
      exStats.value = {
        booths: ov.booths || 0,
        products: ov.products || 0,
        matches: ov.matches?.total || 0,
      }
    } else if (isOrganizer.value) {
      const ov = await dashboardApi.getStatsOverview()
      orgStats.value = {
        exhibitions: ov.total_exhibitions || 0,
        booths: ov.total_booths || 0,
        users: ov.total_users || 0,
      }
    } else {
      const [reg, proc, msg] = await Promise.all([
        registrationApi.getMy({ page_size: 1 }),
        procurementApi.getMyProcurements({ page_size: 1 }),
        messageApi.getUnreadCount(),
      ])
      stats.value = {
        registrations: (reg as any).total || 0,
        procurements: (proc as any).total || 0,
        unread: (msg as any).count || 0,
      }
    }
  } catch (err) {
    // 静默：统计失败不影响页面
  }
}

function goLogin() {
  uni.navigateTo({ url: '/pages/auth/login' })
}

function goDashboard() {
  uni.navigateTo({ url: '/pages/buyer/dashboard' })
}

// 数字卡片点击 → 对应列表
function goStats(key: 'registrations' | 'procurements' | 'messages') {
  if (key === 'messages') {
    uni.switchTab({ url: '/pages/messages/list' })
  } else {
    uni.navigateTo({ url: key === 'registrations' ? '/pages/mine/registrations' : '/pages/mine/procurements' })
  }
}

// 这四个入口的页面都需要登录态，未登录先跳登录页
function requireLogin(): boolean {
  if (userStore.isLoggedIn) return true
  uni.navigateTo({ url: '/pages/auth/login' })
  return false
}

function goRegistrations() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/mine/registrations' })
}

function goProcurements() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/mine/procurements' })
}

function goProfile() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/mine/profile' })
}

function goSettings() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/mine/settings' })
}

// 展商角色入口
function goExDashboard() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/exhibitor/dashboard' })
}
function goExBooths() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/exhibitor/booths' })
}
function goExProducts() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/exhibitor/products' })
}
function goExMatches() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/exhibitor/matches' })
}

// 主办方角色入口
function goOrgDashboard() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/organizer/dashboard' })
}
function goOrgExhibitions() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/organizer/exhibitions' })
}
function goOrgBooths() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/organizer/booths' })
}
function goOrgRegistrations() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/organizer/registrations' })
}
function goOrgStatistics() {
  if (requireLogin()) uni.navigateTo({ url: '/pages/organizer/statistics' })
}

function handleLogout() {
  uni.showModal({
    title: '提示',
    content: '确定退出登录吗？',
    success: ({ confirm }) => {
      if (confirm) {
        userStore.logout()
        uni.showToast({ title: '已退出登录', icon: 'none' })
        setTimeout(() => {
          uni.switchTab({ url: '/pages/index/index' })
        }, 300)
      }
    },
  })
}
</script>

<template>
  <view class="mine-page">
    <!-- 已登录：个人信息卡 -->
    <view v-if="userStore.isLoggedIn" class="profile-card">
      <image
        v-if="userStore.profile?.avatar_url"
        class="avatar"
        :src="userStore.profile.avatar_url"
        mode="aspectFill"
      />
      <view v-else class="avatar avatar-placeholder">
        <text class="avatar-emoji">🙂</text>
      </view>

      <view class="profile-info">
        <view class="name-row">
          <text class="nickname">{{ displayName }}</text>
          <text class="tag" :class="roleTagCls">{{ roleLabel }}</text>
        </view>
        <text class="text-secondary text-sm username">@{{ userStore.profile?.username || '' }}</text>
        <view v-if="totalPoints !== null" class="points-row">
          <text class="points-icon">💎</text>
          <text class="points-text">商业积分 {{ totalPoints }}</text>
        </view>
      </view>
    </view>

    <!-- 数字卡片（已登录） -->
    <view v-if="userStore.isLoggedIn" class="stats-row">
      <!-- 展商角色：展位/展品/采购匹配 -->
      <template v-if="isExhibitor">
        <StatsCard
          title="我的展位"
          :value="exStats.booths"
          icon="🏠"
          color="#3b82f6"
          @click="goExBooths"
        />
        <StatsCard
          title="展品总数"
          :value="exStats.products"
          icon="📦"
          color="#10b981"
          @click="goExProducts"
        />
        <StatsCard
          title="采购匹配"
          :value="exStats.matches"
          icon="🤝"
          :color="exStats.matches > 0 ? '#ef4444' : ''"
          @click="goExMatches"
        />
      </template>
      <!-- 主办方角色：展会/展位/用户 -->
      <template v-else-if="isOrganizer">
        <StatsCard
          title="展会总数"
          :value="orgStats.exhibitions"
          icon="🎪"
          color="#3b82f6"
          @click="goOrgExhibitions"
        />
        <StatsCard
          title="展位总数"
          :value="orgStats.booths"
          icon="🏠"
          color="#8b5cf6"
          @click="goOrgBooths"
        />
        <StatsCard
          title="平台用户"
          :value="orgStats.users"
          icon="👥"
          color="#10b981"
          @click="goOrgStatistics"
        />
      </template>
      <!-- 其他角色：已报名/采购/未读 -->
      <template v-else>
        <StatsCard
          title="已报名展会"
          :value="stats.registrations"
          icon="📋"
          color="#3b82f6"
          @click="goStats('registrations')"
        />
        <StatsCard
          title="采购需求"
          :value="stats.procurements"
          icon="📦"
          color="#10b981"
          @click="goStats('procurements')"
        />
        <StatsCard
          title="未读消息"
          :value="stats.unread"
          icon="📬"
          :color="stats.unread > 0 ? '#ef4444' : ''"
          @click="goStats('messages')"
        />
      </template>
    </view>

    <!-- 未登录 -->
    <view v-else class="profile-card profile-card-login">
      <view class="avatar avatar-placeholder">
        <text class="avatar-emoji">👤</text>
      </view>
      <view class="profile-info">
        <text class="nickname">未登录</text>
        <text class="text-secondary text-sm username">登录后查看报名、采购等信息</text>
        <view class="btn btn-primary btn-sm login-btn" @click="goLogin">点击登录</view>
      </view>
    </view>

    <!-- 快捷入口 -->
    <view class="card menu-card">
      <!-- 主办方角色菜单 -->
      <template v-if="isOrganizer">
        <view class="menu-item" @click="goOrgDashboard">
          <text class="menu-icon">🏢</text>
          <view class="menu-body">
            <text class="menu-title">主办方工作台</text>
            <text class="menu-desc text-secondary text-sm">数据概览与快捷操作</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="goOrgExhibitions">
          <text class="menu-icon">🎪</text>
          <view class="menu-body">
            <text class="menu-title">展会管理</text>
            <text class="menu-desc text-secondary text-sm">创建与编辑展会</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="goOrgBooths">
          <text class="menu-icon">🏠</text>
          <view class="menu-body">
            <text class="menu-title">展位管理</text>
            <text class="menu-desc text-secondary text-sm">新建展位、分配展商</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="goOrgRegistrations">
          <text class="menu-icon">📋</text>
          <view class="menu-body">
            <text class="menu-title">报名管理</text>
            <text class="menu-desc text-secondary text-sm">查看展会报名情况</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="goOrgStatistics">
          <text class="menu-icon">📊</text>
          <view class="menu-body">
            <text class="menu-title">数据统计</text>
            <text class="menu-desc text-secondary text-sm">展会状态与数量分布</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
      </template>
      <!-- 展商角色菜单 -->
      <template v-else-if="isExhibitor">
        <view class="menu-item" @click="goExDashboard">
          <text class="menu-icon">🏠</text>
          <view class="menu-body">
            <text class="menu-title">展商工作台</text>
            <text class="menu-desc text-secondary text-sm">数据概览与快捷操作</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="goExBooths">
          <text class="menu-icon">🏪</text>
          <view class="menu-body">
            <text class="menu-title">我的展位</text>
            <text class="menu-desc text-secondary text-sm">查看已入驻的展位</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="goExProducts">
          <text class="menu-icon">📦</text>
          <view class="menu-body">
            <text class="menu-title">我的展品</text>
            <text class="menu-desc text-secondary text-sm">管理展品与添加新品</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="goExMatches">
          <text class="menu-icon">🤝</text>
          <view class="menu-body">
            <text class="menu-title">采购匹配</text>
            <text class="menu-desc text-secondary text-sm">响应采购需求</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
      </template>
      <!-- 买家/其他角色菜单 -->
      <template v-else>
        <view class="menu-item" @click="goDashboard">
          <text class="menu-icon">🏠</text>
          <view class="menu-body">
            <text class="menu-title">买家中心</text>
            <text class="menu-desc text-secondary text-sm">工作台、快捷操作与最近动态</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="goRegistrations">
          <text class="menu-icon">📋</text>
          <view class="menu-body">
            <text class="menu-title">我的报名</text>
            <text class="menu-desc text-secondary text-sm">查看已报名的展会</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
        <view class="menu-item" @click="goProcurements">
          <text class="menu-icon">📦</text>
          <view class="menu-body">
            <text class="menu-title">我的采购</text>
            <text class="menu-desc text-secondary text-sm">管理我的采购需求</text>
          </view>
          <text class="menu-arrow">›</text>
        </view>
      </template>
      <view class="menu-item" @click="goProfile">
        <text class="menu-icon">👤</text>
        <view class="menu-body">
          <text class="menu-title">个人资料</text>
          <text class="menu-desc text-secondary text-sm">编辑昵称、公司等信息</text>
        </view>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-item" @click="goSettings">
        <text class="menu-icon">⚙️</text>
        <view class="menu-body">
          <text class="menu-title">设置</text>
          <text class="menu-desc text-secondary text-sm">修改密码、退出登录</text>
        </view>
        <text class="menu-arrow">›</text>
      </view>
    </view>

    <!-- 退出登录 -->
    <view v-if="userStore.isLoggedIn" class="btn btn-block logout-btn" @click="handleLogout">
      退出登录
    </view>
  </view>
</template>

<style scoped>
.mine-page {
  padding: 24rpx;
}

.stats-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.profile-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 32rpx 24rpx;
  background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
  border-radius: var(--radius);
  color: #fff;
  margin-bottom: 24rpx;
}

.avatar {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  flex-shrink: 0;
  background-color: rgba(255, 255, 255, 0.25);
}

.avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2rpx solid rgba(255, 255, 255, 0.5);
}

.avatar-emoji {
  font-size: 56rpx;
}

.profile-info {
  flex: 1;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
  flex-wrap: wrap;
}

.nickname {
  font-size: 40rpx;
  font-weight: 700;
  color: #fff;
}

.username {
  opacity: 0.85;
  display: block;
  margin-bottom: 8rpx;
  color: #fff;
}

.points-row {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  background: rgba(255, 255, 255, 0.2);
  padding: 4rpx 16rpx;
  border-radius: 999rpx;
}

.points-icon {
  font-size: 24rpx;
}

.points-text {
  font-size: 24rpx;
  color: #fff;
}

.profile-card-login .username {
  margin-bottom: 16rpx;
}

.login-btn {
  align-self: flex-start;
  background: #fff;
  color: #2563eb;
}

.menu-card {
  margin-bottom: 24rpx;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 24rpx;
  border-bottom: 1px solid var(--color-border);
}

.menu-item:last-child {
  border-bottom: none;
}

.menu-icon {
  font-size: 36rpx;
  width: 48rpx;
  text-align: center;
  flex-shrink: 0;
}

.menu-body {
  flex: 1;
  min-width: 0;
}

.menu-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 4rpx;
}

.menu-desc {
  display: block;
}

.menu-arrow {
  font-size: 40rpx;
  color: #cbd5e1;
  flex-shrink: 0;
}

.web-tip {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
}

.web-tip-icon {
  font-size: 32rpx;
  flex-shrink: 0;
}

.web-tip-text {
  font-size: 26rpx;
  color: var(--color-text-secondary);
  flex: 1;
}

.logout-btn {
  background: #fff;
  color: var(--color-danger);
  border: 1px solid var(--color-border);
}
</style>
