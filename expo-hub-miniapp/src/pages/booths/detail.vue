<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import StatusTag from '@/components/StatusTag.vue'
import ProductCard from '@/components/ProductCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { boothApi, type Booth } from '@/api/booth'
import { productApi, type Product } from '@/api/product'

const id = ref(0)
const booth = ref<Booth | null>(null)
const products = ref<Product[]>([])
const loading = ref(true)
const applying = ref(false)

onLoad((options) => {
  id.value = Number(options?.id || 0)
  loadDetail()
})

async function loadDetail() {
  loading.value = true
  try {
    const [boothRes, productRes] = await Promise.all([
      boothApi.getById(id.value),
      productApi.getList({ booth_id: id.value, page: 1, page_size: 20 }),
    ])
    booth.value = boothRes
    products.value = (productRes as any).list || productRes.items || productRes.results || []
  } catch (err) {
    console.error('Failed to load booth detail:', err)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function handleApply() {
  if (!booth.value || applying.value) return
  applying.value = true
  try {
    await boothApi.apply(booth.value.id)
    // 申请后本地把状态置为待审核,隐藏申请按钮
    booth.value.status = 'pending'
    uni.showToast({ title: '申请成功，请等待审核', icon: 'none' })
  } catch (err: any) {
    // 401 时请求层会自动跳登录,这里只提示失败原因
    uni.showToast({ title: err?.message || '申请失败', icon: 'none' })
  } finally {
    applying.value = false
  }
}

function goToProduct(productId: number) {
  uni.navigateTo({ url: '/pages/products/detail?id=' + productId })
}
</script>

<template>
  <view class="page-wrapper" v-if="loading">
    <LoadingSkeleton :lines="6" />
  </view>

  <view class="page-wrapper" v-else-if="!booth">
    <view class="card card-body">
      <text class="text-secondary">展位不存在</text>
    </view>
  </view>

  <view v-else class="page-wrapper">
    <view class="card">
      <view class="card-body">
        <view class="flex justify-between items-start mb-4">
          <text class="booth-title">展位 {{ booth.booth_number }}</text>
          <StatusTag :status="booth.status" />
        </view>
        <view class="booth-info">
          <view class="info-row">
            <text class="text-secondary">公司名称:</text>
            <text>{{ booth.company_name || '未分配' }}</text>
          </view>
          <view class="info-row">
            <text class="text-secondary">展商:</text>
            <text>{{ booth.exhibitor_name || '未分配' }}</text>
          </view>
          <view class="info-row">
            <text class="text-secondary">面积:</text>
            <text>{{ booth.size || '-' }}</text>
          </view>
          <view class="info-row">
            <text class="text-secondary">区域:</text>
            <text>{{ booth.location_area || '-' }}</text>
          </view>
          <view class="info-row">
            <text class="text-secondary">价格:</text>
            <text>{{ booth.price ? '¥' + booth.price : '-' }}</text>
          </view>
        </view>
        <text v-if="booth.description" class="booth-desc text-secondary mt-4">{{ booth.description }}</text>
        <view v-if="booth.status === 'available'" class="mt-4">
          <view class="btn btn-primary" @click="handleApply">
            <text>{{ applying ? '提交中...' : '申请此展位' }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 展品 -->
    <view class="mt-6">
      <text class="section-title">展品</text>
      <EmptyState v-if="products.length === 0" message="暂无展品" icon="📦" />
      <view v-else class="product-list">
        <ProductCard
          v-for="product in products"
          :key="product.id"
          :product="product"
          @click="goToProduct(product.id)"
        />
      </view>
    </view>
  </view>
</template>

<style scoped>
.booth-title {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.3;
  flex: 1;
  padding-right: 12px;
}

.booth-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
}

.info-row {
  display: flex;
  gap: 8px;
}

.info-row .text-secondary {
  flex-shrink: 0;
}

.booth-desc {
  line-height: 1.8;
  white-space: pre-wrap;
  display: block;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  display: block;
  margin-bottom: 16px;
}

.product-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}
</style>
