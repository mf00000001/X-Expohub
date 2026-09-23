<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import StatsCard from '@/components/StatsCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { dashboardApi } from '@/api/dashboard'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

interface RecentExh {
  id: number
  title: string
  status: string
  start_date?: string
  end_date?: string
  location?: string
  organizer_name?: string
}

const loading = ref(true)
const error = ref('')
const notLoggedIn = ref(false)

const total = ref(0)
const byStatus = ref<Record<string, number>>({})
const recent = ref<RecentExh[]>([])

const statusMap: Record<string, string> = {
  draft: '草稿',
  pending: '待审批',
  published: '已发布',
  active: '进行中',
  ended: '已结束',
  cancelled: '已取消',
  rejected: '已驳回',
}

const statusTagCls: Record<string, string> = {
  published: 'tag-green',
  active: 'tag-blue',
  draft: 'tag-gray',
  pending: 'tag-yellow',
  cancelled: 'tag-red',
  rejected: 'tag-red',
}

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
    const res = (await dashboardApi.getExhibitionStats()) as any
    total.value = res.total || 0
    byStatus.value = res.by_status || {}
    recent.value = res.recent || []
  } catch (err: any) {
    error.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goLogin() {
  uni.navigateTo({ url: '/pages/auth/login' })
}

function goExhibition(id: number) {
  uni.navigateTo({ url: `/pages/exhibitions/detail?id=${id}` })
}
</script>

<template>
  <view class="page-wrapper">
    <view v-if="notLoggedIn" class="card p-6 text-center">
      <text class="text-secondary">请先登录后查看数据统计</text>
      <view class="btn btn-primary mt-4" @click="goLogin">去登录</view>
    </view>

    <view v-else-if="loading" class="loading-container">
      <view class="spinner"></view>
    </view>

    <view v-else-if="error" class="card p-6 text-center">
      <text class="text-danger">{{ error }}</text>
      <view class="btn btn-primary mt-4" @click="fetchData">重试</view>
    </view>

    <template v-else>
      <!-- 展会总数卡片 -->
      <view class="stats-row">
        <StatsCard title="展会总数" :value="total" icon="🎪" color="#3b82f6" />
      </view>

      <!-- 状态分布 -->
      <view class="card mb-6">
        <view class="card-header">
          <text class="font-semibold">展会状态分布</text>
        </view>
        <view class="card-body">
          <view v-if="Object.keys(byStatus).length === 0" class="text-center py-2">
            <text class="text-secondary text-sm">暂无数据</text>
          </view>
          <view v-else class="flex flex-wrap gap-2">
            <view v-for="(count, st) in byStatus" :key="st" class="status-chip">
              <text class="tag" :class="statusTagCls[st] || 'tag-gray'">{{ statusMap[st] || st }}</text>
              <text class="status-count">{{ count }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 各展会统计 -->
      <view class="card">
        <view class="card-header">
          <text class="font-semibold">最近展会</text>
        </view>
        <view class="card-body">
          <EmptyState v-if="recent.length === 0" message="暂无展会" icon="🎪" />
          <view v-else>
            <view v-for="exh in recent" :key="exh.id" class="row" @click="goExhibition(exh.id)">
              <view class="row-info flex-1">
                <view class="flex justify-between items-center">
                  <text class="row-title">{{ exh.title }}</text>
                  <text class="tag" :class="statusTagCls[exh.status] || 'tag-gray'">
                    {{ statusMap[exh.status] || exh.status }}
                  </text>
                </view>
                <text class="row-meta text-sm text-secondary">
                  📅 {{ exh.start_date || '' }}{{ exh.end_date ? ` ~ ${exh.end_date}` : '' }}
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

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 12rpx;
  background: var(--color-bg);
  border-radius: 12rpx;
  padding: 16rpx 20rpx;
}

.status-count {
  font-size: 28rpx;
  font-weight: 700;
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
  flex: 1;
  min-width: 0;
  margin-right: 12rpx;
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
