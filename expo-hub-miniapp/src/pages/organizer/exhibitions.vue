<script setup lang="ts">
import { ref } from 'vue'
import { onShow, onReachBottom } from '@dcloudio/uni-app'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

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

const loading = ref(true)
const error = ref('')
const list = ref<Exhibition[]>([])
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
    const res = (await exhibitionApi.getList({ page: p, page_size: 20 })) as any
    const items = (res.list || res.items || res.results || []) as Exhibition[]
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

// 是否可编辑/删除（本人创建的展会或管理员）
function canManage(exh: Exhibition): boolean {
  const profile = userStore.profile
  if (!profile) return false
  if (profile.role === 'admin') return true
  return exh.organizer_id !== undefined && profile.id === exh.organizer_id
}

function goDetail(exh: Exhibition) {
  uni.navigateTo({ url: `/pages/exhibitions/detail?id=${exh.id}` })
}

function goEdit(exh: Exhibition) {
  uni.navigateTo({ url: `/pages/organizer/exhibition-edit?id=${exh.id}` })
}

function goCreate() {
  uni.navigateTo({ url: '/pages/organizer/exhibition-edit' })
}

function handleDelete(exh: Exhibition) {
  uni.showModal({
    title: '提示',
    content: `确定删除展会「${exh.title}」吗？`,
    success: async ({ confirm }) => {
      if (!confirm) return
      try {
        await exhibitionApi.delete(exh.id)
        uni.showToast({ title: '已删除', icon: 'success' })
        fetchList(true)
      } catch (err: any) {
        uni.showToast({ title: err?.message || '删除失败', icon: 'none' })
      }
    },
  })
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
      <EmptyState message="暂无展会，点击下方按钮新建" icon="🎪" />
    </view>

    <view v-else class="flex flex-col gap-4 pb-20">
      <view v-for="exh in list" :key="exh.id" class="card">
        <view class="card-body">
          <view class="flex justify-between items-center mb-2">
            <text class="exh-title" @click="goDetail(exh)">{{ exh.title }}</text>
            <text class="tag" :class="statusTagCls[exh.status] || 'tag-gray'">
              {{ statusMap[exh.status] || exh.status }}
            </text>
          </view>
          <text class="text-secondary text-sm block">
            📅 {{ exh.start_date }} ~ {{ exh.end_date }}
          </text>
          <text class="text-secondary text-sm block mt-2">📍 {{ exh.location }}</text>
          <text v-if="exh.organizer_name" class="text-secondary text-sm block mt-2">
            🏢 {{ exh.organizer_name }}
          </text>

          <view class="flex gap-2 mt-4">
            <view class="btn btn-outline btn-sm flex-1" @click="goDetail(exh)">查看</view>
            <view v-if="canManage(exh)" class="btn btn-primary btn-sm flex-1" @click="goEdit(exh)">编辑</view>
            <view v-if="canManage(exh)" class="btn btn-sm flex-1 delete-btn" @click="handleDelete(exh)">删除</view>
          </view>
        </view>
      </view>

      <view v-if="hasMore" class="text-center py-4">
        <text class="text-secondary text-sm" @click="loadMore">{{ loadingMore ? '加载中...' : '点击加载更多' }}</text>
      </view>
      <view v-else class="text-center py-4">
        <text class="text-secondary text-sm">— 共 {{ total }} 个展会 —</text>
      </view>
    </view>

    <!-- 底部新建按钮 -->
    <view v-if="!loading && !error" class="add-bar">
      <view class="btn btn-primary btn-lg btn-block" @click="goCreate">➕ 新建展会</view>
    </view>
  </view>
</template>

<style scoped>
.exh-title {
  font-size: 16px;
  font-weight: 600;
  flex: 1;
  min-width: 0;
}

.block {
  display: block;
}

.delete-btn {
  background: #fff;
  color: var(--color-danger);
  border: 1px solid var(--color-border);
}

.add-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 20rpx 32rpx calc(20rpx + env(safe-area-inset-bottom));
  background: #fff;
  box-shadow: 0 -2rpx 16rpx rgba(0, 0, 0, 0.06);
  z-index: 10;
}
</style>
