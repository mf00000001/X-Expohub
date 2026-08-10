<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import ProductCard from '@/components/ProductCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { productApi, type Product } from '@/api/product'

const router = useRouter()
const products = ref<Product[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

async function fetchProducts() {
  loading.value = true
  error.value = ''
  try {
    const res = await productApi.getMyProducts({
      page: currentPage.value,
      page_size: 9,
    })
    products.value = res.items || res.results || res.data || []
    totalPages.value = res.total_pages || Math.ceil((res.total || 0) / 9) || 1
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载展品列表失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchProducts)

function goToDetail(id: number) {
  router.push({ name: 'product-detail', params: { id } })
}

function goToCreate() {
  router.push({ name: 'exhibitor-product-create' })
}

function changePage(page: number) {
  currentPage.value = page
  fetchProducts()
  window.scrollTo(0, 0)
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">我的展品</h1>
        <div class="flex gap-2">
          <button class="btn btn-outline btn-sm" @click="router.push('/exhibitor/dashboard')">
            ← 返回工作台
          </button>
          <button class="btn btn-primary" @click="goToCreate">+ 添加展品</button>
        </div>
      </div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchProducts">重试</button>
      </div>

      <EmptyState v-else-if="products.length === 0" message="暂未添加展品" icon="📦">
        <button class="btn btn-primary mt-4" @click="goToCreate">立即添加</button>
      </EmptyState>

      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <ProductCard
          v-for="product in products"
          :key="product.id"
          :product="product"
          @click="goToDetail(product.id)"
        />
      </div>

      <div v-if="totalPages > 1" class="pagination">
        <button :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
        <button
          v-for="page in totalPages"
          :key="page"
          :class="{ active: page === currentPage }"
          @click="changePage(page)"
        >{{ page }}</button>
        <button :disabled="currentPage >= totalPages" @click="changePage(currentPage + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>
