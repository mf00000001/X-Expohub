<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import SearchBar from '@/components/SearchBar.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import ProductCard from '@/components/ProductCard.vue'
import ProcurementCard from '@/components/ProcurementCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { productApi, type Product } from '@/api/product'
import { procurementApi, type Procurement } from '@/api/procurement'

const route = useRoute()
const router = useRouter()
const searchKeyword = ref((route.query.q as string) || '')
const exhibitions = ref<Exhibition[]>([])
const products = ref<Product[]>([])
const procurements = ref<Procurement[]>([])
const loading = ref(false)
const searched = ref(false)

onMounted(() => {
  if (searchKeyword.value) {
    doSearch(searchKeyword.value)
  }
})

async function handleSearch(value: string) {
  searchKeyword.value = value
  if (!value) {
    exhibitions.value = []
    products.value = []
    procurements.value = []
    searched.value = false
    return
  }
  doSearch(value)
}

async function doSearch(q: string) {
  loading.value = true
  searched.value = true
  try {
    const [expRes, prodRes, procRes] = await Promise.all([
      exhibitionApi.getList({ search: q, page_size: 4 }),
      productApi.getList({ search: q, page_size: 4 }),
      procurementApi.getList({ search: q, page_size: 4 }),
    ])
    exhibitions.value = expRes.items || expRes.results || expRes.data || []
    products.value = prodRes.items || prodRes.results || prodRes.data || []
    procurements.value = procRes.items || procRes.results || procRes.data || []
  } catch (err) {
    console.error('Search error:', err)
  } finally {
    loading.value = false
  }
}

function goToExhibition(id: number) {
  router.push({ name: 'exhibition-detail', params: { id } })
}
function goToProduct(id: number) {
  router.push({ name: 'product-detail', params: { id } })
}
function goToProcurement(id: number) {
  router.push({ name: 'procurement-detail', params: { id } })
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <div class="mb-6" style="max-width:600px">
        <SearchBar v-model="searchKeyword" @search="handleSearch" />
      </div>

      <LoadingSkeleton v-if="loading" :lines="6" />

      <div v-else-if="searched && exhibitions.length === 0 && products.length === 0 && procurements.length === 0">
        <EmptyState message="未找到相关结果" icon="🔍" />
      </div>

      <div v-else-if="searched">
        <!-- Exhibitions -->
        <section v-if="exhibitions.length > 0" class="mb-6">
          <h2 class="text-xl font-bold mb-4">展会</h2>
          <div class="grid grid-cols-1 grid-cols-2 gap-4">
            <ExpoCard v-for="e in exhibitions" :key="e.id" :exhibition="e" @click="goToExhibition(e.id)" />
          </div>
        </section>

        <!-- Products -->
        <section v-if="products.length > 0" class="mb-6">
          <h2 class="text-xl font-bold mb-4">展品</h2>
          <div class="grid grid-cols-1 grid-cols-2 grid-cols-3 grid-cols-4 gap-4">
            <ProductCard v-for="p in products" :key="p.id" :product="p" @click="goToProduct(p.id)" />
          </div>
        </section>

        <!-- Procurements -->
        <section v-if="procurements.length > 0" class="mb-6">
          <h2 class="text-xl font-bold mb-4">采购需求</h2>
          <div class="grid grid-cols-1 grid-cols-2 gap-4">
            <ProcurementCard v-for="p in procurements" :key="p.id" :procurement="p" @click="goToProcurement(p.id)" />
          </div>
        </section>
      </div>

      <div v-else class="text-center text-secondary p-8">
        <p class="text-lg">输入关键词搜索展会、展品或采购需求</p>
      </div>
    </div>
  </div>
</template>
