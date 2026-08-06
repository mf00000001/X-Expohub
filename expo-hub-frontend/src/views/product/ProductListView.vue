<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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
const totalItems = ref(0)

const paginateRange = computed(() => {
  const t = totalPages.value; const c = currentPage.value
  if (t <= 7) return Array.from({length: t}, (_, i) => i + 1)
  const r: (number|string)[] = [1]
  if (c > 3) r.push('...')
  for (let i = Math.max(2, c-1); i <= Math.min(t-1, c+1); i++) r.push(i)
  if (c < t-2) r.push('...')
  r.push(t)
  return r
})

async function fetchProducts() {
  loading.value = true
  try {
    const res = await productApi.getList({
      page: currentPage.value,
      page_size: 12,
      search: searchKeyword.value || undefined,
    })
    products.value = res.list || res.items || res.results || []
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

      <div v-if="totalPages > 1" class="paginate">
        <span class="pag-info">共 {{ (products as any).total || totalPages * 12 }} 件</span>
        <button :disabled="currentPage <= 1" @click="changePage(1)">首页</button>
        <button :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">‹</button>
        <template v-for="p in paginateRange" :key="p">
          <span v-if="p === '...'" class="pag-dots">…</span>
          <button v-else :class="{ active: p === currentPage }" @click="changePage(p as number)">{{ p }}</button>
        </template>
        <button :disabled="currentPage >= totalPages" @click="changePage(currentPage + 1)">›</button>
        <button :disabled="currentPage >= totalPages" @click="changePage(totalPages)">末页</button>
      </div>
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

.paginate { display:flex; align-items:center; justify-content:center; gap:6px; margin-top:32px; flex-wrap:wrap }
.paginate button { padding:6px 12px; border:1px solid var(--color-border); border-radius:6px; background:#fff; cursor:pointer; font-size:13px; min-width:36px }
.paginate button.active { background:var(--color-primary); color:#fff; border-color:var(--color-primary); font-weight:700 }
.paginate button:disabled { opacity:0.4; cursor:default }
.pag-info { font-size:13px; color:var(--color-text-secondary); margin-right:12px }
.pag-dots { padding:0 4px; color:var(--color-text-secondary) }
</style>
