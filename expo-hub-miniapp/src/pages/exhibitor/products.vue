<script setup lang="ts">
import { ref } from 'vue'
import { onShow, onReachBottom } from '@dcloudio/uni-app'
import { productApi, type Product } from '@/api/product'
import ProductCard from '@/components/ProductCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(true)
const error = ref('')
const list = ref<Product[]>([])
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
    const res = (await productApi.getMyProducts({ page: p, page_size: 10 })) as any
    const items = (res.list || res.items || res.results || []) as Product[]
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

function goEdit(prod: Product) {
  uni.navigateTo({ url: `/pages/exhibitor/product-edit?id=${prod.id}` })
}

function goAdd() {
  uni.navigateTo({ url: '/pages/exhibitor/product-edit' })
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
      <EmptyState message="暂无展品，点击下方按钮添加" icon="📦" />
    </view>

    <view v-else class="flex flex-col gap-4 pb-20">
      <ProductCard v-for="prod in list" :key="prod.id" :product="prod" @click="goEdit(prod)" />

      <view v-if="hasMore" class="text-center py-4">
        <text class="text-secondary text-sm" @click="loadMore">{{ loadingMore ? '加载中...' : '点击加载更多' }}</text>
      </view>
      <view v-else class="text-center py-4">
        <text class="text-secondary text-sm">— 共 {{ total }} 个展品 —</text>
      </view>
    </view>

    <!-- 底部添加按钮 -->
    <view v-if="!loading && !error" class="add-bar">
      <view class="btn btn-primary btn-lg btn-block" @click="goAdd">➕ 添加展品</view>
    </view>
  </view>
</template>

<style scoped>
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
