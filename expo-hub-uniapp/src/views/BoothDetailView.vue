<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import StatusTag from '@/components/StatusTag.vue'
import ProductCard from '@/components/ProductCard.vue'
import EmptyState from '@/components/EmptyState.vue'
import { boothApi, type Booth } from '@/api/booth'
import { productApi, type Product } from '@/api/product'
import { reviewApi, type Review } from '@/api/review'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const booth = ref<Booth | null>(null)
const products = ref<Product[]>([])
const reviews = ref<Review[]>([])
const loading = ref(true)

const reviewContent = ref('')
const reviewRating = ref(5)
const submittingReview = ref(false)

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const [boothRes, productRes, reviewRes] = await Promise.all([
      boothApi.getById(id),
      productApi.getList({ booth_id: id, page: 1, page_size: 20 }),
      reviewApi.getList({ target_type: 'booth', target_id: id }),
    ])
    booth.value = boothRes
    products.value = productRes.items || productRes.results || productRes.data || []
    reviews.value = reviewRes.items || reviewRes.results || reviewRes.data || []
  } catch (err) {
    console.error('Failed to load booth detail:', err)
  } finally {
    loading.value = false
  }
})

async function handleApply() {
  if (!userStore.isLoggedIn) {
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  try {
    await boothApi.apply(Number(route.params.id))
    showToast('申请成功，请等待审核')
  } catch (err: any) {
    showToast(err?.response?.data?.detail || '申请失败', 'error')
  }
}

async function submitReview() {
  if (!reviewContent.value.trim()) return
  submittingReview.value = true
  try {
    await reviewApi.create({
      target_type: 'booth',
      target_id: Number(route.params.id),
      rating: reviewRating.value,
      content: reviewContent.value,
    })
    reviewContent.value = ''
    showToast('评价成功！')
    const reviewRes = await reviewApi.getList({ target_type: 'booth', target_id: Number(route.params.id) })
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

function goToProduct(id: number) {
  router.push({ name: 'product-detail', params: { id } })
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper" v-if="loading">
      <LoadingSkeleton :lines="6" />
    </div>
    <div v-else-if="!booth" class="container page-wrapper"><p>展位不存在</p></div>
    <div v-else class="container page-wrapper">
      <div class="breadcrumb">
        <router-link to="/">首页</router-link>
        <span>/</span>
        <span>展位 {{ booth.booth_number }}</span>
      </div>

      <div class="card">
        <div class="card-body">
          <div class="flex justify-between items-start mb-4">
            <h1 class="text-2xl font-bold">展位 {{ booth.booth_number }}</h1>
            <StatusTag :status="booth.status" />
          </div>
          <div class="grid grid-cols-1 grid-cols-2 gap-4 text-sm">
            <div><span class="text-secondary">公司名称：</span>{{ booth.company_name || '未分配' }}</div>
            <div><span class="text-secondary">展商：</span>{{ booth.exhibitor_name || '未分配' }}</div>
            <div><span class="text-secondary">面积：</span>{{ booth.size || '-' }}</div>
            <div><span class="text-secondary">区域：</span>{{ booth.location_area || '-' }}</div>
            <div><span class="text-secondary">价格：</span>{{ booth.price ? '¥' + booth.price : '-' }}</div>
          </div>
          <p class="mt-4 text-secondary" v-if="booth.description">{{ booth.description }}</p>
          <div class="mt-4" v-if="booth.status === 'available'">
            <button class="btn btn-primary" @click="handleApply">申请此展位</button>
          </div>
        </div>
      </div>

      <!-- Products -->
      <div class="mt-6">
        <h2 class="text-xl font-bold mb-4">展品</h2>
        <EmptyState v-if="products.length === 0" message="暂无展品" icon="📦" />
        <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 grid-cols-4 gap-4">
          <ProductCard
            v-for="product in products"
            :key="product.id"
            :product="product"
            @click="goToProduct(product.id)"
          />
        </div>
      </div>

      <!-- Reviews -->
      <div class="mt-6">
        <h2 class="text-xl font-bold mb-4">评价</h2>
        <div v-if="userStore.isLoggedIn" class="card card-body mb-4">
          <div class="form-group">
            <label class="form-label">评分</label>
            <select v-model="reviewRating" class="form-input" style="width:auto">
              <option :value="5">⭐⭐⭐⭐⭐</option>
              <option :value="4">⭐⭐⭐⭐</option>
              <option :value="3">⭐⭐⭐</option>
              <option :value="2">⭐⭐</option>
              <option :value="1">⭐</option>
            </select>
          </div>
          <div class="form-group">
            <textarea v-model="reviewContent" class="form-input form-textarea" placeholder="写下你的评价..."></textarea>
          </div>
          <button class="btn btn-primary btn-sm" :disabled="submittingReview" @click="submitReview">
            {{ submittingReview ? '提交中...' : '提交评价' }}
          </button>
        </div>
        <div v-if="reviews.length === 0" class="text-secondary text-sm">暂无评价</div>
        <div v-else v-for="review in reviews" :key="review.id" class="card card-body mb-3">
          <div class="flex justify-between items-center mb-2">
            <span class="font-semibold">{{ review.reviewer_name || '用户' }}</span>
            <span class="text-sm text-secondary">{{ '⭐'.repeat(review.rating) }}</span>
          </div>
          <p class="text-sm text-secondary">{{ review.content }}</p>
          <p class="text-sm text-secondary mt-1">{{ review.created_at }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
