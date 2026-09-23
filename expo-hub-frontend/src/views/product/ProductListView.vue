<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ProductCard from '@/components/ProductCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import PaginationBar from '@/components/PaginationBar.vue'
import { productApi, type ProductItem as Product } from '@/api/product'

const PAGE_SIZE_KEY = 'product-list-page-size'
const router = useRouter()
const products = ref<Product[]>([])
const loading = ref(true)
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(Number(localStorage.getItem(PAGE_SIZE_KEY)) || 12)
const totalItems = ref(0)
const totalPages = ref(1)

async function fetchProducts() {
  loading.value = true
  try {
    const res = await productApi.getList({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchKeyword.value || undefined,
    })
    products.value = res.list || res.items || res.results || []
    // 真实总数：此前写成 (products as any).total —— 数组上没有 total，
    // 于是「共 N 件」退化成「总页数 × 每页条数」，末页会虚报条数。
    totalItems.value = Number(res.total ?? products.value.length) || products.value.length
    totalPages.value = Number(res.total_pages ?? res.totalPages ?? 0)
      || Math.max(1, Math.ceil(totalItems.value / pageSize.value))
  } catch (err) {
    console.error('Failed to load products:', err)
  } finally {
    loading.value = false
  }
}

onMounted(fetchProducts)

function handleSearch(value: string) {
  searchKeyword.value = value
  currentPage.value = 1
  fetchProducts()
}

function goToDetail(id: number) {
  router.push({ name: 'product-detail', params: { id } })
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <h1 class="page-title">展品列表</h1>
      <div class="mb-6" style="max-width:500px">
        <SearchBar v-model="searchKeyword" @search="handleSearch" />
      </div>

      <LoadingSkeleton v-if="loading" :lines="6" />
      <EmptyState v-else-if="products.length === 0" message="暂无展品" icon="📦" />
      <div v-else class="product-grid">
        <ProductCard
          v-for="product in products"
          :key="product.id"
          :product="product"
          @click="goToDetail(product.id)"
        />
      </div>

      <PaginationBar
        v-if="!loading && products.length"
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :total="totalItems"
        :total-pages="totalPages"
        :loading="loading"
        unit="件展品"
        :page-size-options="[12, 24, 48, 96]"
        storage-key="product-list-page-size"
        @change="fetchProducts"
      />
    </div>
  </div>
</template>

<style scoped>
.product-grid {
  display: grid;
  grid-template-columns: repeat(1, 1fr);
  gap: 16px;
}
@media (min-width: 640px) { .product-grid { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1024px) { .product-grid { grid-template-columns: repeat(3, 1fr); } }
@media (min-width: 1280px) { .product-grid { grid-template-columns: repeat(4, 1fr); } }
</style>
