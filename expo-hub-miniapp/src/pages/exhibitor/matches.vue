<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { recommendationApi, type ProcurementRecommendation } from '@/api/recommendation'
import { productApi, type Product } from '@/api/product'
import { procurementApi } from '@/api/procurement'
import EmptyState from '@/components/EmptyState.vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(true)
const error = ref('')
const list = ref<ProcurementRecommendation[]>([])

// 响应弹窗状态
const showModal = ref(false)
const current = ref<ProcurementRecommendation | null>(null)
const myProducts = ref<Product[]>([])
const productOptions = ref<string[]>(['不指定展品'])
const productIndex = ref(0)
const quotedPrice = ref('')
const message = ref('')
const submitting = ref(false)

onShow(() => {
  if (!userStore.isLoggedIn) {
    loading.value = false
    return
  }
  fetchList()
})

async function fetchList() {
  loading.value = true
  error.value = ''
  try {
    const data = (await recommendationApi.forExhibitor(20)) as unknown as
      | ProcurementRecommendation[]
      | { list?: ProcurementRecommendation[] }
    list.value = Array.isArray(data) ? data : ((data as any).list || (data as any).items || [])
  } catch (err: any) {
    error.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function openRespond(item: ProcurementRecommendation) {
  current.value = item
  productIndex.value = 0
  quotedPrice.value = ''
  message.value = ''
  showModal.value = true
  if (myProducts.value.length === 0) {
    try {
      const res = (await productApi.getMyProducts({ page: 1, page_size: 50 })) as any
      myProducts.value = res.list || res.items || res.results || []
      productOptions.value = ['不指定展品', ...myProducts.value.map((p) => p.name)]
    } catch (err) {
      // 拉取展品失败仍可只填报价/留言
    }
  }
}

function onProductChange(e: any) {
  productIndex.value = Number(e.detail.value)
}

function closeModal() {
  if (submitting.value) return
  showModal.value = false
  current.value = null
}

async function handleRespond() {
  if (!current.value) return
  if (!quotedPrice.value.trim() && !message.value.trim()) {
    uni.showToast({ title: '请填写报价或留言', icon: 'none' })
    return
  }
  if (submitting.value) return
  submitting.value = true
  uni.showLoading({ title: '提交中' })
  try {
    const payload: Record<string, unknown> = {}
    const prod = myProducts.value[productIndex.value - 1]
    if (prod) payload.product_id = prod.id
    if (quotedPrice.value.trim() !== '') payload.quoted_price = Number(quotedPrice.value)
    if (message.value.trim()) payload.message = message.value.trim()
    await procurementApi.match(current.value.id, payload)
    uni.hideLoading()
    uni.showToast({ title: '响应成功', icon: 'success' })
    showModal.value = false
    current.value = null
    fetchList()
  } catch (err: any) {
    uni.hideLoading()
    uni.showToast({ title: err?.message || '提交失败，请重试', icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <view class="page-wrapper">
    <view v-if="loading" class="loading-container">
      <view class="spinner"></view>
    </view>

    <view v-else-if="error" class="card p-6 text-center">
      <text class="text-danger">{{ error }}</text>
      <view class="btn btn-primary mt-4" @click="fetchList">重试</view>
    </view>

    <view v-else-if="list.length === 0" class="card p-6">
      <EmptyState message="暂无匹配的采购需求" icon="🤝" />
    </view>

    <view v-else class="flex flex-col gap-4">
      <view v-for="item in list" :key="item.id" class="card">
        <view class="card-body">
          <view class="flex justify-between items-center mb-2">
            <text class="rec-title">{{ item.title }}</text>
            <text v-if="item.score" class="score-badge">匹配度 {{ item.score }}</text>
          </view>

          <text class="text-secondary text-sm block mb-2">
            👤 {{ item.purchaser_name || '匿名采购商' }}
            <text v-if="item.budget_max"> · 预算 ¥{{ item.budget_max }}</text>
          </text>

          <text v-if="item.description" class="text-secondary text-sm block mb-2">
            {{ item.description.slice(0, 120) }}{{ item.description.length > 120 ? '...' : '' }}
          </text>

          <view v-if="item.reasons && item.reasons.length" class="flex flex-wrap gap-1 mb-3">
            <text v-for="(r, i) in item.reasons" :key="i" class="tag tag-blue reason-tag">{{ r }}</text>
          </view>

          <view class="btn btn-primary btn-sm btn-block" @click="openRespond(item)">🤝 响应此采购</view>
        </view>
      </view>
    </view>

    <!-- 响应弹窗 -->
    <view v-if="showModal" class="modal-mask" @click="closeModal">
      <view class="modal-body" @click.stop>
        <text class="modal-title">响应采购</text>
        <text v-if="current" class="text-secondary text-sm block mb-3">{{ current.title }}</text>

        <view class="form-group">
          <text class="form-label">报价展品</text>
          <picker :range="productOptions" :value="productIndex" @change="onProductChange">
            <view class="form-input picker-value">
              <text :class="productIndex === 0 ? 'text-secondary' : ''">{{ productOptions[productIndex] }}</text>
            </view>
          </picker>
        </view>

        <view class="form-group">
          <text class="form-label">报价（元）</text>
          <input
            v-model="quotedPrice"
            class="form-input"
            type="digit"
            placeholder="如：888.00"
            cursor-spacing="24"
          />
        </view>

        <view class="form-group">
          <text class="form-label">留言</text>
          <textarea
            v-model="message"
            class="form-input form-textarea"
            placeholder="补充说明：起订量、交货期、公司介绍等"
            cursor-spacing="24"
          />
        </view>

        <view class="flex gap-2 mt-4">
          <view class="btn btn-primary flex-1" :class="{ 'btn-disabled': submitting }" @click="handleRespond">
            <text>{{ submitting ? '提交中...' : '提交响应' }}</text>
          </view>
          <view class="btn btn-outline flex-1" @click="closeModal">
            <text>取消</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.rec-title {
  font-size: 16px;
  font-weight: 600;
  flex: 1;
  min-width: 0;
}

.score-badge {
  font-size: 22rpx;
  color: var(--color-danger);
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 999rpx;
  padding: 4rpx 12rpx;
  flex-shrink: 0;
  margin-left: 12rpx;
}

.block {
  display: block;
}

.reason-tag {
  font-size: 22rpx;
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

.picker-value {
  display: flex;
  align-items: center;
  min-height: 44px;
  box-sizing: border-box;
}
</style>
