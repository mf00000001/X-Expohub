<script setup lang="ts">
import type { Product } from '@/api/product'

defineProps<{
  product: Product
}>()

defineEmits<{
  click: []
}>()
</script>

<template>
  <div class="product-card card" @click="$emit('click')">
    <div class="product-image" v-if="product.images && product.images.length > 0">
      <img :src="product.images[0]" :alt="product.name" />
    </div>
    <div class="product-image-placeholder" v-else>
      <span>📦</span>
    </div>
    <div class="card-body">
      <h3 class="product-name">{{ product.name }}</h3>
      <p class="text-secondary text-sm mt-2">{{ product.description?.slice(0, 80) }}{{ product.description?.length > 80 ? '...' : '' }}</p>
      <div class="flex justify-between items-center mt-4">
        <span class="product-price" v-if="product.price !== undefined && product.price !== null">
          ¥{{ product.price }}{{ product.unit ? ` / ${product.unit}` : '' }}
        </span>
        <span class="tag tag-blue" v-if="product.category">{{ product.category }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.product-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.product-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.product-image {
  height: 180px;
  overflow: hidden;
  background: #f9fafb;
}
.product-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 16px;
}
.product-image-placeholder {
  height: 180px;
  background: #f0fdf4;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
}
.product-name {
  font-size: 16px;
  font-weight: 600;
}
.product-price {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-danger);
}
</style>
