<script setup lang="ts">
import { ref } from 'vue'
import { onShow, onReachBottom } from '@dcloudio/uni-app'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { registrationApi, type Registration } from '@/api/registration'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const exhibitions = ref<Exhibition[]>([])
const exhibitionOptions = ref<string[]>(['选择展会'])
const exhibitionIndex = ref(0)
const exhibitionId = ref<number | null>(null)

const loading = ref(false)
const error = ref('')
const list = ref<Registration[]>([])
const total = ref(0)
const page = ref(1)
const hasMore = ref(false)
const loadingMore = ref(false)

onShow(() => {
  if (!userStore.isLoggedIn) return
  loadExhibitions()
})

async function loadExhibitions() {
  try {
    const res = (await exhibitionApi.getList({ page: 1, page_size: 100 })) as any
    exhibitions.value = res.list || res.items || res.results || []
    exhibitionOptions.value = ['选择展会', ...exhibitions.value.map((e) => e.title)]
  } catch (err) {
    // 静默
  }
}

function onExhibitionChange(e: any) {
  exhibitionIndex.value = Number(e.detail.value)
  const ex = exhibitions.value[exhibitionIndex.value - 1]
  exhibitionId.value = ex ? ex.id : null
  fetchList(true)
}

async function fetchList(reset = false) {
  if (!exhibitionId.value) {
    list.value = []
    total.value = 0
    return
  }
  if (reset) {
    page.value = 1
    hasMore.value = false
    error.value = ''
  }
  const p = page.value
  loading.value = reset
  loadingMore.value = !reset
  try {
    const res = (await registrationApi.getByExhibition(exhibitionId.value, { page: p, page_size: 20 })) as any
    const items = (res.list || res.items || res.results || []) as Registration[]
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
  if (!hasMore.value || loadingMore.value || loading.value) return
  page.value += 1
  fetchList()
}
</script>

<template>
  <view class="page-wrapper">
    <!-- 展会筛选 -->
    <view class="card mb-6">
      <view class="card-body">
        <text class="form-label mb-2">选择展会</text>
        <picker :range="exhibitionOptions" :value="exhibitionIndex" @change="onExhibitionChange">
          <view class="form-input picker-value">
            <text :class="exhibitionIndex === 0 ? 'text-secondary' : ''">{{ exhibitionOptions[exhibitionIndex] }}</text>
          </view>
        </picker>
      </view>
    </view>

    <view v-if="loading" class="loading-container">
      <view class="spinner"></view>
    </view>

    <view v-else-if="error" class="card p-6 text-center">
      <text class="text-danger">{{ error }}</text>
      <view class="btn btn-primary mt-4" @click="fetchList(true)">重试</view>
    </view>

    <view v-else-if="!exhibitionId" class="card p-6">
      <EmptyState message="请选择展会查看报名" icon="📋" />
    </view>

    <view v-else-if="list.length === 0" class="card p-6">
      <EmptyState message="该展会暂无报名" icon="📋" />
    </view>

    <view v-else class="flex flex-col gap-4">
      <view class="card">
        <view class="card-body">
          <view v-for="reg in list" :key="reg.id" class="reg-row">
            <view class="reg-info flex-1">
              <view class="flex justify-between items-center">
                <text class="reg-name">👤 {{ reg.username || '未知用户' }}</text>
                <text v-if="reg.ticket_code" class="text-secondary text-sm">🎫 {{ reg.ticket_code }}</text>
              </view>
              <text v-if="reg.email" class="text-secondary text-sm block mt-1">{{ reg.email }}</text>
              <text v-if="reg.created_at" class="text-secondary text-sm block mt-1">
                🕐 {{ reg.created_at.slice(0, 10) }}
              </text>
            </view>
          </view>
        </view>
      </view>

      <view v-if="hasMore" class="text-center py-4">
        <text class="text-secondary text-sm" @click="loadMore">{{ loadingMore ? '加载中...' : '点击加载更多' }}</text>
      </view>
      <view v-else class="text-center py-4">
        <text class="text-secondary text-sm">— 共 {{ total }} 人报名 —</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.reg-row {
  padding: 20rpx 0;
  border-bottom: 1px solid var(--color-border);
}
.reg-row:last-child {
  border-bottom: none;
}

.reg-name {
  font-size: 15px;
  font-weight: 600;
}

.block {
  display: block;
}

.picker-value {
  display: flex;
  align-items: center;
  min-height: 44px;
  box-sizing: border-box;
}
</style>
