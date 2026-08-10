<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import { productApi, type Product } from '@/api/product'
import { reviewApi, type Review } from '@/api/review'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const product = ref<Product | null>(null)
const reviews = ref<Review[]>([])
const loading = ref(true)
const reviewContent = ref('')
const reviewRating = ref(5)
const submittingReview = ref(false)

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const [prodRes, reviewRes] = await Promise.all([
      productApi.getById(id),
      reviewApi.getList({ target_type: 'product', target_id: id }),
    ])
    product.value = prodRes
    reviews.value = reviewRes.items || reviewRes.results || reviewRes.data || []
  } catch (err) {
    console.error('Failed to load product:', err)
  } finally {
    loading.value = false
  }
})

async function submitReview() {
  if (!reviewContent.value.trim()) return
  submittingReview.value = true
  try {
    await reviewApi.create({
      target_type: 'product',
      target_id: Number(route.params.id),
      rating: reviewRating.value,
      content: reviewContent.value,
    })
    reviewContent.value = ''
    showToast('评价成功！')
    const reviewRes = await reviewApi.getList({ target_type: 'product', target_id: Number(route.params.id) })
    reviews.value = reviewRes.items || reviewRes.results || reviewRes.data || []
  } catch (err: any) {
    showToast(err?.response?.data?.detail || '评价失败', 'error')
  } finally {
    submittingReview.value = false
  }
}

function showToast(message: string, type: 'success' | 'error' = 'success') {
  const toast = document.createElement('div')
  toast.className = `toast toast-${type}`
  toast.textContent = message
  document.body.appendChild(toast)
  setTimeout(() => toast.remove(), 3000)
}

function goToBooth(id: number) {
  router.push({ name: 'booth-detail', params: { id } })
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper" v-if="loading"><LoadingSkeleton :lines="6" /></div>
    <div v-else-if="!product" class="container page-wrapper"><p>展品不存在</p></div>
    <div v-else class="container page-wrapper">
      <div class="breadcrumb">
        <router-link to="/">首页</router-link><span>/</span>
        <router-link to="/products">展品</router-link><span>/</span>
        <span>{{ product.name }}</span>
      </div>

      <div class="layout-two-col">
        <div class="card">
          <div class="product-gallery" v-if="product.images && product.images.length > 0">
            <img :src="product.images[0]" :alt="product.name" />
          </div>
          <div class="product-gallery-placeholder" v-else>📦</div>
        </div>
        <div>
          <div class="card card-body">
            <h1 class="text-2xl font-bold mb-2">{{ product.name }}</h1>
            <span class="tag tag-blue mb-4" v-if="product.category">{{ product.category }}</span>
            <p class="text-2xl font-bold text-danger mb-4" v-if="product.price !== undefined && product.price !== null">
              ¥{{ product.price }}{{ product.unit ? ` / ${product.unit}` : '' }}
            </p>
            <p class="text-secondary mb-4" style="line-height:1.8">{{ product.description }}</p>
            <div class="text-sm text-secondary" v-if="product.exhibitor_name">
              展商：{{ product.exhibitor_name }}
            </div>
            <div class="text-sm text-secondary mt-1" v-if="product.booth_id">
              <a @click="goToBooth(product.booth_id!)" style="cursor:pointer">查看所属展位 →</a>
            </div>
          </div>

          <!-- Reviews -->
          <div class="card mt-4">
            <div class="card-header"><h3 class="font-semibold">评价</h3></div>
            <div class="card-body">
              <div v-if="userStore.isLoggedIn" class="mb-4">
                <select v-model="reviewRating" class="form-input mb-2" style="width:auto">
                  <option :value="5">⭐⭐⭐⭐⭐</option>
                  <option :value="4">⭐⭐⭐⭐</option>
                  <option :value="3">⭐⭐⭐</option>
                  <option :value="2">⭐⭐</option>
                  <option :value="1">⭐</option>
                </select>
                <textarea v-model="reviewContent" class="form-input form-textarea mb-2" placeholder="写下你的评价..."></textarea>
                <button class="btn btn-primary btn-sm" :disabled="submittingReview" @click="submitReview">
                  {{ submittingReview ? '提交中...' : '提交评价' }}
                </button>
              </div>
              <div v-if="reviews.length === 0" class="text-sm text-secondary">暂无评价</div>
              <div v-else v-for="review in reviews" :key="review.id" class="mb-3 pb-3" style="border-bottom:1px solid var(--color-border)">
                <div class="flex justify-between">
                  <span class="font-semibold text-sm">{{ review.reviewer_name || '用户' }}</span>
                  <span class="text-sm">{{ '⭐'.repeat(review.rating) }}</span>
                </div>
                <p class="text-sm text-secondary mt-1">{{ review.content }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.product-gallery {
  height: 350px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f9fafb;
  padding: 20px;
}
.product-gallery img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.product-gallery-placeholder {
  height: 350px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 80px;
  background: #f0fdf4;
}
</style>
