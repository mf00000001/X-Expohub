<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { boothApi, type Booth } from '@/api/booth'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { dashboardApi } from '@/api/dashboard'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const statusMap: Record<string, string> = {
  available: '可申请',
  booked: '已预定',
  occupied: '已占用',
  pending: '待审核',
}

const statusTagCls: Record<string, string> = {
  occupied: 'tag-red',
  booked: 'tag-blue',
  available: 'tag-green',
  pending: 'tag-yellow',
}

const exhibitions = ref<Exhibition[]>([])
const exhibitionOptions = ref<string[]>(['选择展会'])
const exhibitionIndex = ref(0)
const exhibitionId = ref<number | null>(null)

const loading = ref(false)
const error = ref('')
const list = ref<Booth[]>([])

// 分配弹窗
const showAssign = ref(false)
const assignBooth = ref<Booth | null>(null)
const exhibitors = ref<{ id: number; username: string; company_name?: string }[]>([])
const exhibitorOptions = ref<string[]>([])
const exhibitorIndex = ref(0)
const assigning = ref(false)

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
  fetchBooths()
}

async function fetchBooths() {
  if (!exhibitionId.value) {
    list.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = (await boothApi.getList({ exhibition_id: exhibitionId.value, page: 1, page_size: 100 })) as any
    list.value = res.list || res.items || res.results || []
  } catch (err: any) {
    error.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goDetail(booth: Booth) {
  uni.navigateTo({ url: `/pages/booths/detail?id=${booth.id}` })
}

function goCreate() {
  uni.navigateTo({
    url: exhibitionId.value
      ? `/pages/organizer/booth-edit?exhibition_id=${exhibitionId.value}`
      : '/pages/organizer/booth-edit',
  })
}

async function openAssign(booth: Booth) {
  assignBooth.value = booth
  exhibitorIndex.value = 0
  showAssign.value = true
  if (exhibitors.value.length === 0) {
    try {
      const res = (await dashboardApi.getUserList({ role: 'exhibitor', page: 1 })) as any
      const items = res.list || []
      exhibitors.value = items
      exhibitorOptions.value = [
        '选择展商',
        ...items.map((u: any) => `${u.username}${u.company_name ? `（${u.company_name}）` : ''}`),
      ]
    } catch (err) {
      uni.showToast({ title: '展商列表加载失败', icon: 'none' })
    }
  }
}

function onExhibitorChange(e: any) {
  exhibitorIndex.value = Number(e.detail.value)
}

function closeAssign() {
  if (assigning.value) return
  showAssign.value = false
  assignBooth.value = null
}

async function handleAssign() {
  if (!assignBooth.value) return
  const ex = exhibitors.value[exhibitorIndex.value - 1]
  if (!ex) {
    uni.showToast({ title: '请选择展商', icon: 'none' })
    return
  }
  if (assigning.value) return
  assigning.value = true
  uni.showLoading({ title: '分配中' })
  try {
    await boothApi.assign(assignBooth.value.id, { exhibitor_id: ex.id })
    uni.hideLoading()
    uni.showToast({ title: '分配成功', icon: 'success' })
    showAssign.value = false
    assignBooth.value = null
    fetchBooths()
  } catch (err: any) {
    uni.hideLoading()
    uni.showToast({ title: err?.message || '分配失败', icon: 'none' })
  } finally {
    assigning.value = false
  }
}
</script>

<template>
  <view class="page-wrapper">
    <!-- 展会筛选 -->
    <view class="card mb-6">
      <view class="card-body">
        <text class="form-label mb-2">按展会筛选</text>
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
      <view class="btn btn-primary mt-4" @click="fetchBooths">重试</view>
    </view>

    <view v-else-if="!exhibitionId" class="card p-6">
      <EmptyState message="请先选择展会查看展位" icon="🏠" />
    </view>

    <view v-else-if="list.length === 0" class="card p-6">
      <EmptyState message="该展会暂无展位" icon="🏠" />
    </view>

    <view v-else class="flex flex-col gap-4 pb-20">
      <view v-for="booth in list" :key="booth.id" class="card">
        <view class="card-body">
          <view class="flex justify-between items-center mb-2">
            <text class="booth-number" @click="goDetail(booth)">{{ booth.booth_number }}</text>
            <text class="tag" :class="statusTagCls[booth.status] || 'tag-gray'">
              {{ statusMap[booth.status] || booth.status }}
            </text>
          </view>
          <text class="text-secondary text-sm block">
            📍 {{ booth.location_area || '未分区' }}<text v-if="booth.size"> · {{ booth.size }}</text>
          </text>
          <text v-if="booth.company_name" class="text-secondary text-sm block mt-2">🏢 {{ booth.company_name }}</text>
          <text v-else class="text-secondary text-sm block mt-2">👤 未分配展商</text>

          <view class="flex gap-2 mt-4">
            <view class="btn btn-outline btn-sm flex-1" @click="goDetail(booth)">查看</view>
            <view class="btn btn-primary btn-sm flex-1" @click="openAssign(booth)">分配展商</view>
          </view>
        </view>
      </view>
    </view>

    <!-- 底部新建按钮 -->
    <view v-if="!loading && !error" class="add-bar">
      <view class="btn btn-primary btn-lg btn-block" @click="goCreate">➕ 新建展位</view>
    </view>

    <!-- 分配展商弹窗 -->
    <view v-if="showAssign" class="modal-mask" @click="closeAssign">
      <view class="modal-body" @click.stop>
        <text class="modal-title">分配展商</text>
        <text v-if="assignBooth" class="text-secondary text-sm block mb-3">展位 {{ assignBooth.booth_number }}</text>

        <view class="form-group">
          <text class="form-label">选择展商</text>
          <picker :range="exhibitorOptions" :value="exhibitorIndex" @change="onExhibitorChange">
            <view class="form-input picker-value">
              <text :class="exhibitorIndex === 0 ? 'text-secondary' : ''">{{ exhibitorOptions[exhibitorIndex] }}</text>
            </view>
          </picker>
        </view>

        <view class="flex gap-2 mt-4">
          <view class="btn btn-primary flex-1" :class="{ 'btn-disabled': assigning }" @click="handleAssign">
            <text>{{ assigning ? '分配中...' : '确认分配' }}</text>
          </view>
          <view class="btn btn-outline flex-1" @click="closeAssign">
            <text>取消</text>
          </view>
        </view>
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

.picker-value {
  display: flex;
  align-items: center;
  min-height: 44px;
  box-sizing: border-box;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 100;
  display: flex;
  align-items: flex-end;
}

.modal-body {
  width: 100%;
  background: #fff;
  border-radius: 24rpx 24rpx 0 0;
  padding: 32rpx 32rpx calc(32rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-title {
  font-size: 18px;
  font-weight: 700;
  display: block;
  margin-bottom: 8rpx;
}
</style>
