<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import StatsCard from '@/components/StatsCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import ProcurementCard from '@/components/ProcurementCard.vue'
import { registrationApi, type Registration } from '@/api/registration'
import { procurementApi, type Procurement } from '@/api/procurement'
import { messageApi } from '@/api/message'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(true)
const error = ref('')
const notLoggedIn = ref(false)

const regTotal = ref(0)
const procTotal = ref(0)
const unreadCount = ref(0)
const registered = ref<Registration[]>([])
const procurements = ref<Procurement[]>([])

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
    const [regRes, procRes, msgRes] = await Promise.all([
      registrationApi.getMy({ page: 1, page_size: 4 }),
      procurementApi.getMyProcurements({ page: 1, page_size: 4 }),
      messageApi.getUnreadCount(),
    ])
    const regList = ((regRes as any).list || regRes.items || regRes.results || []) as Registration[]
    registered.value = regList
    regTotal.value = (regRes as any).total || regList.length
    const procList = ((procRes as any).list || procRes.items || procRes.results || []) as Procurement[]
    procurements.value = procList
    procTotal.value = (procRes as any).total || procList.length
    unreadCount.value = (msgRes as any).count || 0
  } catch (err: any) {
    error.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goLogin() {
  uni.navigateTo({ url: '/pages/auth/login' })
}

// 数字卡片点击
function goRegistrations() {
  uni.navigateTo({ url: '/pages/mine/registrations' })
}
function goProcurements() {
  uni.navigateTo({ url: '/pages/mine/procurements' })
}
function goMessages() {
  uni.switchTab({ url: '/pages/messages/list' })
}

// 快捷操作
function goBrowse() {
  uni.switchTab({ url: '/pages/exhibitions/list' })
}
function goCreateProcurement() {
  uni.navigateTo({ url: '/pages/procurements/create' })
}

// 最近列表点击
function goExhibition(reg: Registration) {
  const id = reg.exhibition_id || reg.exhibition?.id
  if (id) uni.navigateTo({ url: `/pages/exhibitions/detail?id=${id}` })
}
function goProcurementDetail(proc: Procurement) {
  uni.navigateTo({ url: `/pages/procurements/detail?id=${proc.id}` })
}
</script>

<template>
  <view class="page-wrapper">
    <!-- 未登录 -->
    <view v-if="notLoggedIn" class="card p-6 text-center">
      <text class="text-secondary">请先登录后查看买家中心</text>
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
        <StatsCard title="已报名展会" :value="regTotal" icon="📋" color="#3b82f6" @click="goRegistrations" />
        <StatsCard title="采购需求" :value="procTotal" icon="📦" color="#10b981" @click="goProcurements" />
        <StatsCard title="未读消息" :value="unreadCount" icon="📬" :color="unreadCount > 0 ? '#ef4444' : ''" @click="goMessages" />
      </view>

      <!-- 快捷操作 -->
      <view class="card mb-6">
        <view class="card-header">
          <text class="font-semibold">快捷操作</text>
        </view>
        <view class="card-body">
          <view class="flex flex-col gap-2">
            <view class="btn btn-outline btn-block" @click="goBrowse">🎪 浏览展会市场</view>
            <view class="btn btn-outline btn-block" @click="goRegistrations">📋 我报名的展会</view>
            <view class="btn btn-outline btn-block" @click="goProcurements">📦 我的采购需求</view>
            <view class="btn btn-primary btn-block" @click="goCreateProcurement">➕ 发布新采购需求</view>
          </view>
        </view>
      </view>

      <!-- 最近报名的展会 -->
      <view class="card mb-6">
        <view class="card-header flex justify-between items-center">
          <text class="font-semibold">最近报名的展会</text>
          <text class="btn btn-sm btn-outline" @click="goRegistrations">查看全部 →</text>
        </view>
        <view class="card-body">
          <EmptyState v-if="registered.length === 0" message="暂无报名，去逛逛展会吧" icon="🎪" />
          <view v-else>
            <view
              v-for="reg in registered"
              :key="reg.id"
              class="reg-row"
              @click="goExhibition(reg)"
            >
              <view class="reg-info flex-1">
                <text class="reg-title">{{ reg.exhibition?.title || '未命名展会' }}</text>
                <text v-if="reg.exhibition?.start_date" class="reg-meta text-sm text-secondary">
                  📅 {{ reg.exhibition.start_date }}{{ reg.exhibition.end_date ? ` ~ ${reg.exhibition.end_date}` : '' }}
                </text>
              </view>
              <text class="arrow">→</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 最近采购需求 -->
      <view class="card">
        <view class="card-header flex justify-between items-center">
          <text class="font-semibold">我的采购需求</text>
          <text class="btn btn-sm btn-outline" @click="goProcurements">查看全部 →</text>
        </view>
        <view class="card-body">
          <EmptyState v-if="procurements.length === 0" message="暂无采购需求，立即发布一个" icon="📦" />
          <view v-else class="flex flex-col gap-4">
            <ProcurementCard
              v-for="proc in procurements"
              :key="proc.id"
              :procurement="proc"
              @click="goProcurementDetail(proc)"
            />
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

.reg-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 0;
  border-bottom: 1px solid var(--color-border);
}
.reg-row:last-child {
  border-bottom: none;
}

.reg-title {
  font-size: 15px;
  font-weight: 600;
  display: block;
}

.reg-meta {
  display: block;
  margin-top: 4rpx;
}

.arrow {
  color: var(--color-text-secondary);
  font-size: 18px;
}
</style>
