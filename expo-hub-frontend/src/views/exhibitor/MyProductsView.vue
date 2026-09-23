<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ProductCard from '@/components/ProductCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { productApi, type Product } from '@/api/product'

const router = useRouter()
const products = ref<Product[]>([])
const loading = ref(true)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const PAGE_SIZE_KEY = 'my-products-page-size'
const total = ref(0)
const pageSize = ref(Number(localStorage.getItem(PAGE_SIZE_KEY)) || 9)

async function fetchProducts() {
  loading.value = true
  error.value = ''
  try {
    const res = await productApi.getMyProducts({
      page: currentPage.value,
      page_size: pageSize.value,
    })
    products.value = res.list || res.items || res.results || []
    total.value = Number((res as any).total ?? products.value.length) || products.value.length
    totalPages.value = Number((res as any).totalPages ?? (res as any).total_pages ?? 0)
      || Math.max(1, Math.ceil(total.value / pageSize.value))
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

function goToEdit(id: number) {
  router.push({ name: 'exhibitor-product-edit', params: { id } })
}

async function handleDelete(id: number) {
  const name = products.value.find(p => p.id === id)?.name || `#${id}`
  if (!confirm(`确定删除展品"${name}"？此操作不可恢复。`)) return
  try {
    await productApi.delete(id)
    alert('展品已删除')
    await fetchProducts()
  } catch (e: any) {
    alert(e?.response?.data?.message || e?.response?.data?.detail || '删除失败')
  }
}
</script>

<template>
  <div>
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
          manageable
          @click="goToDetail(product.id)"
          @manage-edit="goToEdit"
          @manage-delete="handleDelete"
        />
      </div>

      <PaginationBar
        v-if="!loading && products.length"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :total-pages="totalPages"
        :loading="loading"
        unit="件展品"
        :page-size-options="[9, 18, 36, 72]"
        storage-key="my-products-page-size"
        @change="fetchProducts"
      />
    </div>
  </div>
</template>
