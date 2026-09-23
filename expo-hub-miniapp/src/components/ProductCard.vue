<script setup lang="ts">
import type { Product } from '@/api/product'
import { isHttpUrl } from '@/utils/image'

defineProps<{
  product: Product
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <view class="product-card card" @click="$emit('click')">
    <image
      v-if="product.images && product.images.length > 0 && isHttpUrl(product.images[0])"
      class="product-image"
      :src="product.images[0]"
      mode="aspectFit"
    />
    <view v-else class="product-image product-image-placeholder">
      <text>📦</text>
    </view>
    <view class="card-body">
      <text class="product-name">{{ product.name }}</text>
      <text class="text-secondary text-sm mt-2 block">
        {{ product.description?.slice(0, 80) }}{{ product.description?.length > 80 ? '...' : '' }}
      </text>
      <view class="flex justify-between items-center mt-4">
        <text v-if="product.price !== undefined && product.price !== null" class="product-price">
          ¥{{ product.price }}{{ product.unit ? ` / ${product.unit}` : '' }}
        </text>
        <text v-if="product.category" class="tag tag-blue">{{ product.category }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.product-image {
  width: 100%;
  height: 360rpx;
  display: block;
  background: #f9fafb;
  padding: 16px;
  box-sizing: border-box;
}

.product-image-placeholder {
  background: #f0fdf4;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
  color: #a7f3d0;
}

.product-name {
  font-size: 16px;
  font-weight: 600;
  display: block;
}

.block {
  display: block;
}

.product-price {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-danger);
}
</style>
