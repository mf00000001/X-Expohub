<template>
  <view class="page-wrapper">
    <LoadingSkeleton v-if="loading" :lines="6" />
    <view v-else-if="!product" class="empty-state">
      <text class="empty-state-icon">📦</text>
      <text class="empty-state-text">展品不存在</text>
    </view>

    <view v-else class="detail-page">
      <!-- 图片轮播 -->
      <swiper
        v-if="product.images && product.images.length > 0"
        class="product-swiper"
        indicator-dots
        indicator-color="rgba(0,0,0,0.2)"
        indicator-active-color="#3b82f6"
        circular
      >
        <swiper-item v-for="(img, index) in product.images" :key="index">
          <image :src="img" class="swiper-image" mode="aspectFit" />
        </swiper-item>
      </swiper>
      <view v-else class="product-swiper product-placeholder">
        <text>📦</text>
      </view>

      <!-- 基本信息 -->
      <view class="card card-body mt-4">
        <text class="product-name">{{ product.name }}</text>
        <view class="flex items-center gap-2 mt-2">
          <text v-if="product.category" class="tag tag-blue">{{ product.category }}</text>
          <text v-if="statusText" class="tag tag-green">{{ statusText }}</text>
        </view>
        <text
          v-if="product.price !== undefined && product.price !== null"
          class="product-price"
        >¥{{ product.price }}{{ product.unit ? ` / ${product.unit}` : '' }}</text>
        <text class="product-desc text-secondary mt-4">{{ product.description }}</text>
      </view>

      <!-- 规格信息 -->
      <view class="card card-body mt-4">
        <text class="section-title">📋 规格信息</text>
        <view v-if="product.category" class="spec-row">
          <text class="spec-label">分类</text>
          <text class="spec-value">{{ product.category }}</text>
        </view>
        <view v-if="product.unit" class="spec-row">
          <text class="spec-label">单位</text>
          <text class="spec-value">{{ product.unit }}</text>
        </view>
        <view v-if="product.stock !== undefined && product.stock !== null" class="spec-row">
          <text class="spec-label">库存</text>
          <text class="spec-value">{{ product.stock }}</text>
        </view>
        <view v-if="product.created_at" class="spec-row">
          <text class="spec-label">上架时间</text>
          <text class="spec-value">{{ product.created_at }}</text>
        </view>
        <view v-if="!product.category && !product.unit && product.stock === undefined && !product.created_at" class="text-sm text-secondary">
          暂无规格信息
        </view>
      </view>

      <!-- 展商信息 -->
      <view class="card card-body mt-4">
        <text class="section-title">🏢 展商信息</text>
        <view class="spec-row">
          <text class="spec-label">展商</text>
          <text class="spec-value">{{ product.exhibitor_name || '未知展商' }}</text>
        </view>
        <view v-if="product.booth_id" class="booth-link" @click="goToBooth(product.booth_id)">
          <text class="booth-link-text">查看所属展位 →</text>
        </view>
      </view>

      <!-- 联系展商 -->
      <view class="contact-bar">
        <view class="btn btn-primary btn-block" :class="{ 'btn-disabled': contacting }" @click="contactExhibitor">
          <text>{{ contacting ? '发起中...' : '💬 联系展商' }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import { productApi, type Product } from '@/api/product'
import { messageApi } from '@/api/message'

const id = ref(0)
const product = ref<Product | null>(null)
const loading = ref(true)
const contacting = ref(false)

const statusText = computed(() => {
  const map: Record<string, string> = {
    published: '已上架',
    draft: '草稿',
    off_shelf: '已下架',
    sold_out: '已售罄',
  }
  return product.value?.status ? map[product.value.status] || product.value.status : ''
})

onLoad((options) => {
  id.value = Number(options?.id || 0)
  fetchProduct()
})

async function fetchProduct() {
  loading.value = true
  try {
    product.value = await productApi.getById(id.value)
  } catch (err) {
    console.error('Failed to load product:', err)
    uni.showToast({ title: (err as any)?.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function goToBooth(boothId: number) {
  uni.navigateTo({ url: `/pages/booths/detail?id=${boothId}` })
}

async function contactExhibitor() {
  const exhibitorId = product.value?.exhibitor_id
  if (!exhibitorId) {
    uni.showToast({ title: '该展品暂无可联系展商', icon: 'none' })
    return
  }
  if (contacting.value) return
  contacting.value = true
  try {
    const conversation = await messageApi.startConversation(exhibitorId, '您好，我对您的产品感兴趣')
    uni.navigateTo({ url: `/pages/messages/conversation?id=${conversation.id}` })
  } catch (err) {
    uni.showToast({ title: (err as any)?.message || '发起会话失败', icon: 'none' })
  } finally {
    contacting.value = false
  }
}
</script>

<style scoped>
.product-swiper {
  width: 100%;
  height: 480rpx;
  background: #f9fafb;
  display: block;
}

.swiper-image {
  width: 100%;
  height: 480rpx;
  box-sizing: border-box;
  padding: 16px;
}

.product-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0fdf4;
  font-size: 80rpx;
  color: #a7f3d0;
}

.product-name {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1.4;
}

.product-price {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: var(--color-danger);
  margin-top: 16rpx;
}

.product-desc {
  display: block;
  line-height: 1.8;
}

.section-title {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 16rpx;
}

.spec-row {
  display: flex;
  align-items: center;
  padding: 10rpx 0;
  border-bottom: 1px solid var(--color-border);
}
.spec-row:last-child {
  border-bottom: none;
}

.spec-label {
  width: 140rpx;
  flex-shrink: 0;
  font-size: 14px;
  color: var(--color-text-secondary);
}

.spec-value {
  flex: 1;
  font-size: 14px;
  color: var(--color-text);
}

.booth-link {
  margin-top: 16rpx;
}

.booth-link-text {
  font-size: 14px;
  color: var(--color-primary);
  font-weight: 500;
}

.contact-bar {
  margin-top: 32rpx;
  padding-bottom: 24rpx;
}
</style>
