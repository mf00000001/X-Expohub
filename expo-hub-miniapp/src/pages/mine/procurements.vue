<script setup lang="ts">
import { ref, computed } from 'vue'
import { onLoad, onReachBottom } from '@dcloudio/uni-app'
import { procurementApi, type Procurement } from '@/api/procurement'
import ProcurementCard from '@/components/ProcurementCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const procurements = ref<Procurement[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const pageSize = 9
const total = ref(0)
const notLoggedIn = ref(false)

const hasMore = computed(() => procurements.value.length < total.value)

async function fetchProcurements(reset = false) {
  if (reset) {
    currentPage.value = 1
    procurements.value = []
  }
  loading.value = true
  error.value = ''
  try {
    const res = await procurementApi.getMyProcurements({
      page: currentPage.value,
      page_size: pageSize,
    })
    const items = ((res as any).list || res.items || res.results || []) as Procurement[]
    total.value = res.total || 0
    procurements.value = reset ? items : [...procurements.value, ...items]
  } catch (err: any) {
    error.value = err?.message || '加载采购需求失败'
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
  fetchProcurements(true)
})

function goLogin() {
  uni.navigateTo({ url: '/pages/auth/login' })
}

onReachBottom(() => {
  if (hasMore.value && !loading.value) {
    currentPage.value += 1
    fetchProcurements()
  }
})

function goToDetail(id: number) {
  uni.navigateTo({ url: `/pages/procurements/detail?id=${id}` })
}

function goToCreate() {
  uni.navigateTo({ url: '/pages/procurements/create' })
}
</script>

<template>
  <view class="page-wrapper">
    <view v-if="!notLoggedIn" class="flex justify-between items-center mb-4 header">
      <text class="page-title header-title">我的采购需求</text>
      <view class="btn btn-primary btn-sm" @click="goToCreate">+ 发布采购</view>
    </view>

    <!-- 未登录 -->
    <view v-if="notLoggedIn" class="card p-6 text-center">
      <text class="text-secondary">请先登录后查看采购需求</text>
      <view class="btn btn-primary mt-4" @click="goLogin">去登录</view>
    </view>

    <!-- 加载 -->
    <view v-else-if="loading && procurements.length === 0" class="loading-container">
      <view class="spinner"></view>
    </view>

    <!-- 错误 -->
    <view v-else-if="error" class="card p-6 text-center">
      <text class="text-danger">{{ error }}</text>
      <view class="btn btn-primary mt-4" @click="fetchProcurements(true)">重试</view>
    </view>

    <!-- 空 -->
    <EmptyState v-else-if="procurements.length === 0" message="暂未发布采购需求" icon="📦" />

    <!-- 列表 -->
    <view v-else class="proc-list">
      <ProcurementCard
        v-for="item in procurements"
        :key="item.id"
        :procurement="item"
        @click="goToDetail(item.id)"
      />

      <view class="load-more text-center">
        <text v-if="loading" class="text-secondary text-sm">加载中...</text>
        <text v-else-if="!hasMore" class="text-secondary text-sm">没有更多了</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.header-title {
  margin-bottom: 0;
  font-size: 36rpx;
}

.proc-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.load-more {
  padding: 20rpx 0;
}
</style>
