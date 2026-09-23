<script setup lang="ts">
import { ref } from 'vue'
import { onShow, onReachBottom } from '@dcloudio/uni-app'
import { boothApi, type Booth } from '@/api/booth'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const statusMap: Record<string, string> = {
  available: '可预订',
  booked: '已预订',
  occupied: '已入驻',
  pending: '审核中',
  rejected: '被驳回',
  cancelled: '已取消',
}

const statusTagCls: Record<string, string> = {
  occupied: 'tag-green',
  available: 'tag-gray',
  booked: 'tag-blue',
  pending: 'tag-yellow',
  rejected: 'tag-red',
}

const loading = ref(true)
const error = ref('')
const list = ref<Booth[]>([])
const total = ref(0)
const page = ref(1)
const hasMore = ref(false)
const loadingMore = ref(false)

onShow(() => {
  if (!userStore.isLoggedIn) {
    loading.value = false
    return
  }
  fetchList(true)
})

async function fetchList(reset = false) {
  if (reset) {
    page.value = 1
    hasMore.value = false
    error.value = ''
  }
  const p = page.value
  try {
    const res = (await boothApi.getMyBooths({ page: p, page_size: 10 })) as any
    const items = (res.list || res.items || res.results || []) as Booth[]
    total.value = res.total || items.length
    list.value = reset ? items : list.value.concat(items)
    hasMore.value = list.value.length < total.value
  } catch (err: any) {
    if (reset) error.value = err?.message || '加载失败'
    else uni.showToast({ title: err?.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function loadMore() {
  if (!hasMore.value || loadingMore.value) return
  page.value += 1
  loadingMore.value = true
  fetchList()
}

function goDetail(booth: Booth) {
  uni.navigateTo({ url: `/pages/booths/detail?id=${booth.id}` })
}
</script>

<template>
  <view class="page-wrapper">
    <view v-if="loading" class="loading-container">
      <view class="spinner"></view>
    </view>

    <view v-else-if="error" class="card p-6 text-center">
      <text class="text-danger">{{ error }}</text>
      <view class="btn btn-primary mt-4" @click="fetchList(true)">重试</view>
    </view>

    <view v-else-if="list.length === 0" class="card p-6">
      <EmptyState message="暂无展位，可在展位列表申请入驻" icon="🏠" />
    </view>

    <view v-else class="flex flex-col gap-4">
      <view v-for="booth in list" :key="booth.id" class="card" @click="goDetail(booth)">
        <view class="card-body">
          <view class="flex justify-between items-center mb-2">
            <text class="booth-number">{{ booth.booth_number }}</text>
            <text class="tag" :class="statusTagCls[booth.status] || 'tag-gray'">
              {{ statusMap[booth.status] || booth.status }}
            </text>
          </view>
          <text class="text-secondary text-sm block">
            📍 {{ booth.location_area || '未分区' }}<text v-if="booth.size"> · {{ booth.size }}</text>
          </text>
          <text v-if="booth.description" class="text-secondary text-sm block mt-2">
            {{ booth.description }}
          </text>
        </view>
      </view>

      <view v-if="hasMore" class="text-center py-4">
        <text class="text-secondary text-sm" @click="loadMore">{{ loadingMore ? '加载中...' : '点击加载更多' }}</text>
      </view>
      <view v-else class="text-center py-4">
        <text class="text-secondary text-sm">— 共 {{ total }} 个展位 —</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.booth-number {
  font-size: 36rpx;
  font-weight: 700;
  color: var(--color-primary);
}

.block {
  display: block;
}
</style>
