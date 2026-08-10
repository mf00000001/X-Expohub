<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import ProductCard from '@/components/ProductCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { productApi, type Product } from '@/api/product'

const router = useRouter()
const products = ref<Product[]>([])
const loading = ref(true)
const searchKeyword = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

async function fetchProducts() {
  loading.value = true
  try {
    const res = await productApi.getList({
      page: currentPage.value,
      page_size: 12,
      search: searchKeyword.value || undefined,
    })
    products.value = res.items || res.results || res.data || []
    totalPages.value = res.total_pages || Math.ceil((res.total || 0) / 12) || 1
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
      <h1 class="page-title">展品列表</h1>
      <div class="mb-6" style="max-width:500px">
        <SearchBar v-model="searchKeyword" @search="handleSearch" />
      </div>

      <LoadingSkeleton v-if="loading" :lines="6" />
      <EmptyState v-else-if="products.length === 0" message="暂无展品" icon="📦" />
      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 grid-cols-4 gap-4">
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
