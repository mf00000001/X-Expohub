<template>
  <view class="page-wrapper">
    <LoadingSkeleton v-if="loading" :lines="6" />
    <view v-else-if="!procurement" class="empty-state">
      <text class="empty-state-icon">📋</text>
      <text class="empty-state-text">采购需求不存在</text>
    </view>

    <view v-else class="detail-page">
      <!-- 采购需求详情 -->
      <view class="card card-body">
        <view class="flex justify-between items-start mb-4">
          <text class="detail-title">{{ procurement.title }}</text>
          <StatusTag :status="procurement.status" />
        </view>
        <view class="detail-grid">
          <view v-if="procurement.purchaser_name" class="detail-item">
            <text class="text-secondary">采购方：</text>
            <text>{{ procurement.purchaser_name }}</text>
          </view>
          <view v-if="procurement.category" class="detail-item">
            <text class="text-secondary">分类：</text>
            <text>{{ procurement.category }}</text>
          </view>
          <view v-if="procurement.quantity" class="detail-item">
            <text class="text-secondary">数量：</text>
            <text>{{ procurement.quantity }}{{ procurement.unit ? ` ${procurement.unit}` : '' }}</text>
          </view>
          <view v-if="procurement.budget" class="detail-item">
            <text class="text-secondary">预算：</text>
            <text>¥{{ procurement.budget }}</text>
          </view>
          <view v-if="procurement.deadline" class="detail-item">
            <text class="text-secondary">截止日期：</text>
            <text>{{ procurement.deadline }}</text>
          </view>
          <view v-if="procurement.exhibition_title" class="detail-item">
            <text class="text-secondary">关联展会：</text>
            <text>{{ procurement.exhibition_title }}</text>
          </view>
        </view>
        <text class="detail-desc text-secondary">{{ procurement.description }}</text>
      </view>

      <!-- 联系发布人 -->
      <view class="contact-bar">
        <view class="btn btn-primary btn-block" :class="{ 'btn-disabled': contacting }" @click="contactPurchaser">
          <text>{{ contacting ? '发起中...' : '💬 联系发布人' }}</text>
        </view>
      </view>

      <!-- 匹配展品 -->
      <view v-if="matches.length > 0" class="matches-section">
        <text class="section-title">📦 匹配展品</text>
        <view class="match-list">
          <ProductCard
            v-for="product in matches"
            :key="product.id"
            :product="product"
            @click="goToProduct(product.id)"
          />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { procurementApi, type Procurement } from '@/api/procurement'
import { messageApi } from '@/api/message'
import type { Product } from '@/api/product'
import StatusTag from '@/components/StatusTag.vue'
import ProductCard from '@/components/ProductCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'

const procurement = ref<Procurement | null>(null)
const matches = ref<Product[]>([])
const loading = ref(true)
const contacting = ref(false)

onLoad((options) => {
  const id = Number(options?.id || 0)
  fetchDetail(id)
})

async function fetchDetail(id: number) {
  loading.value = true
  try {
    const [procRes, matchRes] = await Promise.all([
      procurementApi.getById(id),
      procurementApi.getMatches(id).catch(() => null),
    ])
    procurement.value = procRes
    if (matchRes) {
      const raw = matchRes as any
      matches.value = Array.isArray(raw)
        ? raw
        : raw.list || raw.items || raw.results || raw.data || []
    }
  } catch (err: any) {
    uni.showToast({ title: err?.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function contactPurchaser() {
  const purchaserId = procurement.value?.purchaser_id
  if (!purchaserId) {
    uni.showToast({ title: '暂无发布人联系方式', icon: 'none' })
    return
  }
  if (contacting.value) return
  contacting.value = true
  try {
    const conversation = await messageApi.startConversation(
      purchaserId,
      `您好，我对您的采购需求「${procurement.value?.title || ''}」感兴趣，想进一步了解。`,
    )
    uni.navigateTo({ url: `/pages/messages/conversation?id=${conversation.id}` })
  } catch (err: any) {
    uni.showToast({ title: err?.message || '发起会话失败', icon: 'none' })
  } finally {
    contacting.value = false
  }
}

function goToProduct(id: number) {
  uni.navigateTo({ url: `/pages/products/detail?id=${id}` })
}
</script>

<style scoped>
.detail-title {
  flex: 1;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--color-text);
  margin-right: 16rpx;
}

.detail-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 32px;
  margin-bottom: 24rpx;
  font-size: 14px;
}

.detail-item {
  flex: 1 1 200rpx;
  min-width: 200rpx;
}

.detail-desc {
  display: block;
  line-height: 1.8;
  white-space: pre-wrap;
}

.contact-bar {
  margin-top: 32rpx;
  padding-bottom: 24rpx;
}

.matches-section {
  margin-top: 32rpx;
}

.section-title {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 16rpx;
}

.match-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
