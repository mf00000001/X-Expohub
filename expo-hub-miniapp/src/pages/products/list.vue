<template>
  <view class="page-wrapper">
    <!-- 搜索 -->
    <view class="mb-6">
      <SearchBar v-model="searchKeyword" placeholder="搜索展品名称、分类..." @search="handleSearch" />
    </view>

    <LoadingSkeleton v-if="loading" :lines="6" />
    <EmptyState v-else-if="products.length === 0" message="暂无展品" icon="📦" />
    <view v-else class="product-list">
      <ProductCard
        v-for="product in products"
        :key="product.id"
        :product="product"
        @click="goToDetail(product.id)"
      />
    </view>

    <!-- 分页状态 -->
    <view v-if="loadingMore" class="load-more">
      <text>加载中...</text>
    </view>
    <view v-else-if="hasMore && products.length > 0" class="load-more">
      <text>上拉加载更多</text>
    </view>
    <view v-else-if="!hasMore && products.length > 0" class="load-more">
      <text>— 已经到底啦 —</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onReachBottom } from '@dcloudio/uni-app'
import ProductCard from '@/components/ProductCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { productApi, type Product } from '@/api/product'

const PAGE_SIZE = 10

const products = ref<Product[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const searchKeyword = ref('')
const currentPage = ref(1)
const total = ref(0)
const hasMore = ref(true)

const exhibitionId = ref<number>()
const boothId = ref<number>()

onLoad((options) => {
  exhibitionId.value = Number(options?.exhibition_id || 0) || undefined
  boothId.value = Number(options?.booth_id || 0) || undefined
  fetchProducts(true)
})

async function fetchProducts(reset = false) {
  if (reset) {
    currentPage.value = 1
    hasMore.value = true
  }
  if (loadingMore.value) return

  if (reset) {
    loading.value = true
  } else {
    loadingMore.value = true
  }

  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: PAGE_SIZE,
    }
    if (exhibitionId.value) params.exhibition_id = exhibitionId.value
    if (boothId.value) params.booth_id = boothId.value
    if (searchKeyword.value.trim()) params.search = searchKeyword.value.trim()

    const res = await productApi.getList(params)
    const list = (res as any).list || res.items || res.results || []
    if (reset) {
      products.value = list
    } else {
      products.value = products.value.concat(list)
    }
    total.value = res.total || 0
    hasMore.value = currentPage.value * PAGE_SIZE < total.value
    currentPage.value += 1
  } catch (err) {
    console.error('Failed to load products:', err)
    uni.showToast({ title: (err as any)?.message || '加载失败', icon: 'none' })
    if (reset) products.value = []
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function handleSearch(value: string) {
  searchKeyword.value = value
  fetchProducts(true)
}

function goToDetail(id: number) {
  uni.navigateTo({ url: `/pages/products/detail?id=${id}` })
}

onReachBottom(() => {
  if (hasMore.value && !loading.value) {
    fetchProducts(false)
  }
})
</script>

<style scoped>
.product-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.load-more {
  text-align: center;
  padding: 24rpx 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}
</style>
