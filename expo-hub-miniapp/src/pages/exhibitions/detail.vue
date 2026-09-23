<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import StatusTag from '@/components/StatusTag.vue'
import EmptyState from '@/components/EmptyState.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { boothApi, type Booth } from '@/api/booth'
import { registrationApi, type Registration } from '@/api/registration'
import { useUserStore } from '@/stores/user'
import { isHttpUrl } from '@/utils/image'

const userStore = useUserStore()

const id = ref(0)
const exhibition = ref<Exhibition | null>(null)
const booths = ref<Booth[]>([])
const loading = ref(true)
const registered = ref(false)
const registering = ref(false)

onLoad((options) => {
  id.value = Number(options?.id || 0)
  loadDetail()
})

async function loadDetail() {
  loading.value = true
  try {
    const [expRes, boothRes] = await Promise.all([
      exhibitionApi.getById(id.value),
      boothApi.getList({ exhibition_id: id.value, page: 1, page_size: 50 }),
    ])
    exhibition.value = expRes
    booths.value = (boothRes as any).list || boothRes.items || boothRes.results || []
    await checkRegistered()
  } catch (err) {
    console.error('Failed to load exhibition detail:', err)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

// 通过我的报名列表判断当前用户是否已报名该展会
async function checkRegistered() {
  if (!userStore.isLoggedIn) return
  try {
    const res = await registrationApi.getMy({ page_size: 100 })
    const items: Registration[] = (res as any).list || res.items || res.results || []
    registered.value = items.some((r) => Number(r.exhibition_id) === id.value)
  } catch (err) {
    // 未登录/会话失效等情况静默处理,按钮以未报名态展示
    console.error('Failed to check registration:', err)
    registered.value = false
  }
}

async function toggleRegister() {
  if (!exhibition.value || registering.value) return
  registering.value = true
  try {
    if (registered.value) {
      await registrationApi.cancel(exhibition.value.id)
      registered.value = false
      uni.showToast({ title: '已取消报名', icon: 'success' })
    } else {
      await registrationApi.create({ exhibition_id: exhibition.value.id })
      registered.value = true
      uni.showToast({ title: '报名成功！', icon: 'success' })
    }
  } catch (err: any) {
    // 401 时请求层会自动跳登录,这里只提示失败原因
    uni.showToast({ title: err?.message || '操作失败', icon: 'none' })
  } finally {
    registering.value = false
  }
}

// 后端状态: draft/pending/published/ongoing/ended/cancelled
// 可报名的状态: published(已发布), ongoing(进行中)
function canRegister(status: string): boolean {
  return status === 'published' || status === 'ongoing'
}

function goToBooth(boothId: number) {
  uni.navigateTo({ url: '/pages/booths/detail?id=' + boothId })
}

function goToProducts() {
  uni.navigateTo({ url: '/pages/products/list?exhibition_id=' + id.value })
}
</script>

<template>
  <view class="page-wrapper" v-if="loading">
    <LoadingSkeleton :lines="8" />
  </view>

  <view class="page-wrapper" v-else-if="!exhibition">
    <view class="card card-body">
      <text class="text-secondary">展会不存在</text>
    </view>
  </view>

  <view v-else class="page-wrapper">
    <view class="card">
      <image
        v-if="isHttpUrl(exhibition.cover_image)"
        class="exhibition-cover"
        :src="exhibition.cover_image"
        mode="aspectFill"
      />
      <view class="card-body">
        <view class="flex justify-between items-start mb-4">
          <text class="exhibition-title">{{ exhibition.title }}</text>
          <StatusTag :status="exhibition.status" />
        </view>
        <view class="flex meta-row text-sm text-secondary mb-4">
          <text>📅 {{ exhibition.start_date }} ~ {{ exhibition.end_date }}</text>
          <text>📍 {{ exhibition.location }}</text>
          <text v-if="exhibition.organizer_name">👤 {{ exhibition.organizer_name }}</text>
        </view>
        <text class="exhibition-desc text-secondary">{{ exhibition.description }}</text>

        <view v-if="canRegister(exhibition.status)" class="mt-6 register-area">
          <view
            :class="['btn', registered ? 'btn-outline' : 'btn-primary']"
            @click="toggleRegister"
          >
            <text>{{ registering ? '处理中...' : (registered ? '已报名,点击取消' : '立即报名') }}</text>
          </view>
          <text v-if="registered" class="registered-hint text-sm text-success">✓ 你已报名该展会</text>
        </view>
      </view>
    </view>

    <!-- 展品入口 -->
    <view class="card card-body entry-row flex justify-between items-center" @click="goToProducts">
      <view>
        <text class="entry-title">📦 展品浏览</text>
        <view class="entry-desc text-sm text-secondary">查看本展会全部展品</view>
      </view>
      <text class="arrow">→</text>
    </view>

    <!-- 展位列表 -->
    <view class="mt-6">
      <text class="section-title">展位列表</text>
      <EmptyState v-if="booths.length === 0" message="暂无展位" icon="🏠" />
      <view v-else class="booth-list">
        <view
          v-for="booth in booths"
          :key="booth.id"
          class="card card-body booth-card"
          @click="goToBooth(booth.id)"
        >
          <view class="flex justify-between items-center">
            <text class="font-semibold">{{ booth.booth_number }}</text>
            <StatusTag :status="booth.status" />
          </view>
          <view v-if="booth.company_name" class="text-sm text-secondary mt-2">{{ booth.company_name }}</view>
          <view v-if="booth.size" class="text-sm text-secondary">面积: {{ booth.size }}</view>
          <view v-if="booth.location_area" class="text-sm text-secondary">区域: {{ booth.location_area }}</view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.exhibition-cover {
  width: 100%;
  height: 360rpx;
  display: block;
  background-color: #f3f4f6;
}

.exhibition-title {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.3;
  flex: 1;
  padding-right: 12px;
}

.meta-row {
  flex-wrap: wrap;
  gap: 16px;
}

.exhibition-desc {
  line-height: 1.8;
  white-space: pre-wrap;
  display: block;
}

.register-area {
  display: flex;
  align-items: center;
  gap: 16px;
}

.registered-hint {
  flex-shrink: 0;
}

.entry-row {
  margin-top: 24px;
  background: #fff;
}

.entry-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
}

.entry-desc {
  margin-top: 4px;
}

.arrow {
  font-size: 20px;
  color: var(--color-text-secondary);
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  display: block;
  margin-bottom: 16px;
}

.booth-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.booth-card {
  background: var(--color-card);
}
</style>
