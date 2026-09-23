<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import StatsCard from '@/components/StatsCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { dashboardApi } from '@/api/dashboard'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(true)
const error = ref('')
const notLoggedIn = ref(false)

const exTotal = ref(0)
const boothTotal = ref(0)
const userTotal = ref(0)
const matchRate = ref(0)
const procTotal = ref(0)
const procMatched = ref(0)
const productTotal = ref(0)
const exhibitorActive = ref(0)
const recentExhibitions = ref<Exhibition[]>([])

onLoad(() => {
  if (!userStore.isLoggedIn) {
    notLoggedIn.value = true
    loading.value = false
    return
  }
  fetchData()
})

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const [ov, exhRes] = await Promise.all([
      dashboardApi.getStatsOverview(),
      exhibitionApi.getList({ page: 1, page_size: 4 }),
    ])
    exTotal.value = ov.total_exhibitions || 0
    boothTotal.value = ov.total_booths || 0
    userTotal.value = ov.total_users || 0
    matchRate.value = ov.procurement_match_rate || 0
    procTotal.value = ov.procurement_total || 0
    procMatched.value = ov.procurement_matched || 0
    productTotal.value = ov.total_products || 0
    exhibitorActive.value = ov.exhibitor_active_count || 0
    recentExhibitions.value = (exhRes as any).list || exhRes.items || exhRes.results || []
  } catch (err: any) {
    error.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goLogin() {
  uni.navigateTo({ url: '/pages/auth/login' })
}

// 数字卡片
function goExhibitions() {
  uni.navigateTo({ url: '/pages/organizer/exhibitions' })
}
function goBooths() {
  uni.navigateTo({ url: '/pages/organizer/booths' })
}
function goStatistics() {
  uni.navigateTo({ url: '/pages/organizer/statistics' })
}

// 快捷操作
function goRegistrations() {
  uni.navigateTo({ url: '/pages/organizer/registrations' })
}
function goCreateExhibition() {
  uni.navigateTo({ url: '/pages/organizer/exhibition-edit' })
}
function goExhibitionDetail(exh: Exhibition) {
  uni.navigateTo({ url: `/pages/exhibitions/detail?id=${exh.id}` })
}
</script>

<template>
  <view class="page-wrapper">
    <!-- 未登录 -->
    <view v-if="notLoggedIn" class="card p-6 text-center">
      <text class="text-secondary">请先登录后查看主办方工作台</text>
      <view class="btn btn-primary mt-4" @click="goLogin">去登录</view>
    </view>

    <!-- 加载 -->
    <view v-else-if="loading" class="loading-container">
      <view class="spinner"></view>
    </view>

    <!-- 错误 -->
    <view v-else-if="error" class="card p-6 text-center">
      <text class="text-danger">{{ error }}</text>
      <view class="btn btn-primary mt-4" @click="fetchData">重试</view>
    </view>

    <template v-else>
      <!-- 数字卡片 -->
      <view class="stats-row">
        <StatsCard title="展会总数" :value="exTotal" icon="🎪" color="#3b82f6" @click="goExhibitions" />
        <StatsCard title="展位总数" :value="boothTotal" icon="🏠" color="#8b5cf6" @click="goBooths" />
        <StatsCard title="平台用户" :value="userTotal" icon="👥" color="#10b981" @click="goStatistics" />
      </view>

      <!-- 运营概览 -->
      <view class="card mb-6">
        <view class="card-header">
          <text class="font-semibold">运营概览</text>
        </view>
        <view class="card-body">
          <view class="ov-grid">
            <view class="ov-item">
              <text class="ov-value">{{ matchRate }}%</text>
              <text class="ov-label text-secondary text-sm">采购匹配率</text>
            </view>
            <view class="ov-item">
              <text class="ov-value">{{ procTotal }}</text>
              <text class="ov-label text-secondary text-sm">采购需求</text>
            </view>
            <view class="ov-item">
              <text class="ov-value">{{ productTotal }}</text>
              <text class="ov-label text-secondary text-sm">展品总数</text>
            </view>
            <view class="ov-item">
              <text class="ov-value">{{ exhibitorActive }}</text>
              <text class="ov-label text-secondary text-sm">活跃展商</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 快捷操作 -->
      <view class="card mb-6">
        <view class="card-header">
          <text class="font-semibold">快捷操作</text>
        </view>
        <view class="card-body">
          <view class="flex flex-col gap-2">
            <view class="btn btn-outline btn-block" @click="goExhibitions">🎪 展会管理</view>
            <view class="btn btn-outline btn-block" @click="goBooths">🏠 展位管理</view>
            <view class="btn btn-outline btn-block" @click="goRegistrations">📋 报名管理</view>
            <view class="btn btn-outline btn-block" @click="goStatistics">📊 数据统计</view>
            <view class="btn btn-primary btn-block" @click="goCreateExhibition">➕ 新建展会</view>
          </view>
        </view>
      </view>

      <!-- 最近展会 -->
      <view class="card">
        <view class="card-header flex justify-between items-center">
          <text class="font-semibold">最近展会</text>
          <text class="btn btn-sm btn-outline" @click="goExhibitions">查看全部 →</text>
        </view>
        <view class="card-body">
          <EmptyState v-if="recentExhibitions.length === 0" message="暂无展会，立即新建一个" icon="🎪" />
          <view v-else>
            <view
              v-for="exh in recentExhibitions"
              :key="exh.id"
              class="row"
              @click="goExhibitionDetail(exh)"
            >
              <view class="row-info flex-1">
                <text class="row-title">{{ exh.title }}</text>
                <text class="row-meta text-sm text-secondary">
                  📅 {{ exh.start_date }} ~ {{ exh.end_date }} · {{ exh.location }}
                </text>
              </view>
              <text class="arrow">→</text>
            </view>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<style scoped>
.stats-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 32rpx;
}

.ov-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
}

.ov-item {
  background: var(--color-bg);
  border-radius: 12rpx;
  padding: 24rpx 16rpx;
  text-align: center;
}

.ov-value {
  display: block;
  font-size: 36rpx;
  font-weight: 700;
  color: var(--color-primary);
  line-height: 1.2;
}

.ov-label {
  display: block;
  margin-top: 4rpx;
}

.row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 0;
  border-bottom: 1px solid var(--color-border);
}
.row:last-child {
  border-bottom: none;
}

.row-title {
  font-size: 15px;
  font-weight: 600;
  display: block;
}

.row-meta {
  display: block;
  margin-top: 4rpx;
}

.arrow {
  color: var(--color-text-secondary);
  font-size: 18px;
}
</style>
