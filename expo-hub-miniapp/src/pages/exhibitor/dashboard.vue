<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import StatsCard from '@/components/StatsCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { dashboardApi } from '@/api/dashboard'
import { boothApi, type Booth } from '@/api/booth'
import { productApi, type Product } from '@/api/product'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(true)
const error = ref('')
const notLoggedIn = ref(false)

const boothTotal = ref(0)
const productTotal = ref(0)
const matchTotal = ref(0)
const matchAccepted = ref(0)
const todayViews = ref(0)
const totalViews = ref(0)
const totalSearches = ref(0)
const totalFavorites = ref(0)
const myBooths = ref<Booth[]>([])
const myProducts = ref<Product[]>([])

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
    const [ov, boothRes, prodRes] = await Promise.all([
      dashboardApi.getExhibitorOverview(),
      boothApi.getMyBooths({ page: 1, page_size: 3 }),
      productApi.getMyProducts({ page: 1, page_size: 3 }),
    ])
    boothTotal.value = ov.booths || 0
    productTotal.value = ov.products || 0
    matchTotal.value = ov.matches?.total || 0
    matchAccepted.value = ov.matches?.accepted || 0
    todayViews.value = ov.today?.views || 0
    totalViews.value = ov.total?.views || 0
    totalSearches.value = ov.total?.searches || 0
    totalFavorites.value = ov.total?.favorites || 0
    myBooths.value = (boothRes as any).list || boothRes.items || boothRes.results || []
    myProducts.value = (prodRes as any).list || prodRes.items || prodRes.results || []
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
function goBooths() {
  uni.navigateTo({ url: '/pages/exhibitor/booths' })
}
function goProducts() {
  uni.navigateTo({ url: '/pages/exhibitor/products' })
}
function goMatches() {
  uni.navigateTo({ url: '/pages/exhibitor/matches' })
}

// 快捷操作
function goAddProduct() {
  uni.navigateTo({ url: '/pages/exhibitor/product-edit' })
}

// 最近列表点击
function goBoothDetail(booth: Booth) {
  uni.navigateTo({ url: `/pages/booths/detail?id=${booth.id}` })
}
function goProductEdit(prod: Product) {
  uni.navigateTo({ url: `/pages/exhibitor/product-edit?id=${prod.id}` })
}
</script>

<template>
  <view class="page-wrapper">
    <!-- 未登录 -->
    <view v-if="notLoggedIn" class="card p-6 text-center">
      <text class="text-secondary">请先登录后查看展商工作台</text>
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
        <StatsCard title="我的展位" :value="boothTotal" icon="🏠" color="#3b82f6" @click="goBooths" />
        <StatsCard title="展品总数" :value="productTotal" icon="📦" color="#10b981" @click="goProducts" />
        <StatsCard title="采购匹配" :value="matchTotal" icon="🤝" :color="matchTotal > 0 ? '#ef4444' : ''" @click="goMatches" />
      </view>

      <!-- 今日概览 -->
      <view class="card mb-6">
        <view class="card-header">
          <text class="font-semibold">今日概览</text>
        </view>
        <view class="card-body">
          <view class="ov-row">
            <view class="ov-item">
              <text class="ov-value">{{ todayViews }}</text>
              <text class="ov-label text-secondary text-sm">今日浏览量</text>
            </view>
            <view class="ov-item">
              <text class="ov-value">{{ totalViews }}</text>
              <text class="ov-label text-secondary text-sm">累计浏览量</text>
            </view>
            <view class="ov-item">
              <text class="ov-value">{{ matchAccepted }}</text>
              <text class="ov-label text-secondary text-sm">已成交匹配</text>
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
            <view class="btn btn-outline btn-block" @click="goBooths">🏠 我的展位</view>
            <view class="btn btn-outline btn-block" @click="goProducts">📦 我的展品</view>
            <view class="btn btn-outline btn-block" @click="goMatches">🤝 采购匹配</view>
            <view class="btn btn-primary btn-block" @click="goAddProduct">➕ 添加新展品</view>
          </view>
        </view>
      </view>

      <!-- 最近展品 -->
      <view class="card mb-6">
        <view class="card-header flex justify-between items-center">
          <text class="font-semibold">最近展品</text>
          <text class="btn btn-sm btn-outline" @click="goProducts">查看全部 →</text>
        </view>
        <view class="card-body">
          <EmptyState v-if="myProducts.length === 0" message="暂无展品，立即添加一个" icon="📦" />
          <view v-else>
            <view
              v-for="prod in myProducts"
              :key="prod.id"
              class="row"
              @click="goProductEdit(prod)"
            >
              <view class="row-info flex-1">
                <text class="row-title">{{ prod.name }}</text>
                <text class="row-meta text-sm text-secondary">
                  {{ prod.category || '未分类' }}<text v-if="prod.status"> · {{ prod.status === 'published' ? '已上架' : '草稿' }}</text>
                </text>
              </view>
              <text class="arrow">→</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 最近展位 -->
      <view class="card">
        <view class="card-header flex justify-between items-center">
          <text class="font-semibold">我的展位</text>
          <text class="btn btn-sm btn-outline" @click="goBooths">查看全部 →</text>
        </view>
        <view class="card-body">
          <EmptyState v-if="myBooths.length === 0" message="暂无展位" icon="🏠" />
          <view v-else>
            <view
              v-for="booth in myBooths"
              :key="booth.id"
              class="row"
              @click="goBoothDetail(booth)"
            >
              <view class="row-info flex-1">
                <text class="row-title">{{ booth.booth_number }}</text>
                <text class="row-meta text-sm text-secondary">
                  {{ booth.location_area || '未分区' }}<text v-if="booth.size"> · {{ booth.size }}</text>
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

.ov-row {
  display: flex;
  gap: 16rpx;
}

.ov-item {
  flex: 1;
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
