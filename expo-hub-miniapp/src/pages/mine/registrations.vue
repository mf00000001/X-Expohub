<script setup lang="ts">
import { ref, computed } from 'vue'
import { onLoad, onReachBottom } from '@dcloudio/uni-app'
import { registrationApi, type Registration } from '@/api/registration'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { isHttpUrl } from '@/utils/image'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const registrations = ref<Registration[]>([])
const loading = ref(true)
const error = ref('')
const notLoggedIn = ref(false)
const currentPage = ref(1)
const pageSize = 9
const total = ref(0)

const hasMore = computed(() => registrations.value.length < total.value)

async function fetchRegistrations(reset = false) {
  if (reset) {
    currentPage.value = 1
    registrations.value = []
  }
  loading.value = true
  error.value = ''
  try {
    const res = await registrationApi.getMy({
      page: currentPage.value,
      page_size: pageSize,
    })
    const items = ((res as any).list || res.items || res.results || []) as Registration[]
    total.value = res.total || 0
    registrations.value = reset ? items : [...registrations.value, ...items]
  } catch (err: any) {
    error.value = err?.message || '加载报名记录失败'
  } finally {
    loading.value = false
  }
}

onLoad(() => {
  // 未登录不发请求，避免 401 噪音
  if (!userStore.isLoggedIn) {
    notLoggedIn.value = true
    loading.value = false
    return
  }
  fetchRegistrations(true)
})

function goLogin() {
  uni.navigateTo({ url: '/pages/auth/login' })
}

onReachBottom(() => {
  if (hasMore.value && !loading.value) {
    currentPage.value += 1
    fetchRegistrations()
  }
})

function goToExhibition(reg: Registration) {
  const id = reg.exhibition_id || reg.exhibition?.id
  if (id) {
    uni.navigateTo({ url: `/pages/exhibitions/detail?id=${id}` })
  }
}

function cancelRegistration(reg: Registration) {
  const id = reg.exhibition_id || reg.exhibition?.id
  if (!id) return
  const title = reg.exhibition?.title || '该展会'
  uni.showModal({
    title: '取消报名',
    content: `确定取消报名「${title}」吗？`,
    success: async ({ confirm }) => {
      if (!confirm) return
      try {
        await registrationApi.cancel(id)
        uni.showToast({ title: '已取消报名', icon: 'success' })
        registrations.value = registrations.value.filter((r) => (r.exhibition_id || r.exhibition?.id) !== id)
      } catch (err: any) {
        uni.showToast({ title: err?.message || '取消失败', icon: 'none' })
      }
    },
  })
}
</script>

<template>
  <view class="page-wrapper">
    <!-- 未登录 -->
    <view v-if="notLoggedIn" class="card p-6 text-center">
      <text class="text-secondary">请先登录后查看报名记录</text>
      <view class="btn btn-primary mt-4" @click="goLogin">去登录</view>
    </view>

    <!-- 加载 -->
    <view v-else-if="loading && registrations.length === 0" class="loading-container">
      <view class="spinner"></view>
    </view>

    <!-- 错误 -->
    <view v-else-if="error" class="card p-6 text-center">
      <text class="text-danger">{{ error }}</text>
      <view class="btn btn-primary mt-4" @click="fetchRegistrations(true)">重试</view>
    </view>

    <!-- 空 -->
    <EmptyState v-else-if="registrations.length === 0" message="暂未报名任何展会" icon="📋" />

    <!-- 列表 -->
    <view v-else class="reg-list">
      <view v-for="reg in registrations" :key="reg.id" class="card reg-card">
        <view class="reg-main" @click="goToExhibition(reg)">
          <image
            v-if="isHttpUrl(reg.exhibition?.cover_image)"
            class="reg-cover"
            :src="reg.exhibition.cover_image"
            mode="aspectFill"
          />
          <view v-else class="reg-cover reg-cover-placeholder">
            <text class="placeholder-icon">🎪</text>
          </view>

          <view class="reg-body">
            <view class="flex justify-between items-start gap-2">
              <text class="reg-title">{{ reg.exhibition?.title || '未命名展会' }}</text>
              <StatusTag :status="reg.exhibition?.status || 'unknown'" />
            </view>
            <text v-if="reg.exhibition?.location" class="text-secondary text-sm reg-line">
              📍 {{ reg.exhibition.location }}
            </text>
            <text v-if="reg.exhibition?.start_date" class="text-secondary text-sm reg-line">
              📅 {{ reg.exhibition.start_date }}{{ reg.exhibition.end_date ? ` ~ ${reg.exhibition.end_date}` : '' }}
            </text>
            <text v-if="reg.exhibition?.organizer_name" class="text-secondary text-sm reg-line">
              👤 {{ reg.exhibition.organizer_name }}
            </text>
            <text v-if="reg.created_at" class="text-secondary text-sm reg-line">报名时间：{{ reg.created_at }}</text>
          </view>
        </view>

        <view class="reg-footer">
          <text v-if="reg.ticket_code" class="text-secondary text-sm ticket-code">🎫 {{ reg.ticket_code }}</text>
          <view class="btn btn-outline btn-sm" @click="cancelRegistration(reg)">取消报名</view>
        </view>
      </view>

      <view class="load-more text-center">
        <text v-if="loading" class="text-secondary text-sm">加载中...</text>
        <text v-else-if="!hasMore" class="text-secondary text-sm">没有更多了</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.reg-card {
  margin-bottom: 20rpx;
}

.reg-main {
  display: flex;
  gap: 20rpx;
}

.reg-cover {
  width: 200rpx;
  height: 160rpx;
  flex-shrink: 0;
  border-radius: 8rpx;
  background-color: #f3f4f6;
}

.reg-cover-placeholder {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-icon {
  font-size: 40rpx;
  opacity: 0.7;
}

.reg-body {
  flex: 1;
  min-width: 0;
  padding: 8rpx 8rpx 8rpx 0;
}

.reg-title {
  font-size: 30rpx;
  font-weight: 600;
  flex: 1;
  line-height: 1.3;
}

.reg-line {
  display: block;
  margin-top: 6rpx;
}

.reg-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx 20rpx;
  border-top: 1px solid var(--color-border);
}

.ticket-code {
  flex: 1;
}

.load-more {
  padding: 20rpx 0;
}
</style>
