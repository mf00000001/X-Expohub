<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import StatusTag from '@/components/StatusTag.vue'
import ProductCard from '@/components/ProductCard.vue'
import { procurementApi, type Procurement } from '@/api/procurement'
import { productApi, type Product } from '@/api/product'
import { useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const procurement = ref<Procurement | null>(null)
const matches = ref<Product[]>([])
const loading = ref(true)

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const [procRes, matchRes] = await Promise.all([
      procurementApi.getById(id),
      procurementApi.getMatches(id).catch(() => ({ items: [] })),
    ])
    procurement.value = procRes
    matches.value = matchRes.items || matchRes.results || matchRes.data || []
  } catch (err) {
    console.error('Failed to load procurement:', err)
  } finally {
    loading.value = false
  }
})

function goToProduct(id: number) {
  router.push({ name: 'product-detail', params: { id } })
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper" v-if="loading"><LoadingSkeleton :lines="6" /></div>
    <div v-else-if="!procurement" class="container page-wrapper"><p>采购需求不存在</p></div>
    <div v-else class="container page-wrapper">
      <div class="breadcrumb">
        <router-link to="/">首页</router-link><span>/</span>
        <router-link to="/procurements">采购需求</router-link><span>/</span>
        <span>{{ procurement.title }}</span>
      </div>

      <div class="card">
        <div class="card-body">
          <div class="flex justify-between items-start mb-4">
            <h1 class="text-2xl font-bold">{{ procurement.title }}</h1>
            <StatusTag :status="procurement.status" />
          </div>
          <div class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-4 text-sm mb-4">
            <div><span class="text-secondary">采购方：</span>{{ procurement.purchaser_name || '未知' }}</div>
            <div v-if="procurement.category"><span class="text-secondary">分类：</span>{{ procurement.category }}</div>
            <div v-if="procurement.quantity"><span class="text-secondary">数量：</span>{{ procurement.quantity }}{{ procurement.unit ? ` ${procurement.unit}` : '' }}</div>
            <div v-if="procurement.budget"><span class="text-secondary">预算：</span>¥{{ procurement.budget }}</div>
            <div v-if="procurement.deadline"><span class="text-secondary">截止日期：</span>{{ procurement.deadline }}</div>
            <div v-if="procurement.exhibition_title"><span class="text-secondary">关联展会：</span>{{ procurement.exhibition_title }}</div>
          </div>
          <p class="text-secondary" style="line-height:1.8;white-space:pre-wrap;">{{ procurement.description }}</p>
        </div>
      </div>

      <!-- Matched Products -->
      <div class="mt-6" v-if="matches.length > 0">
        <h2 class="text-xl font-bold mb-4">匹配展品</h2>
        <div class="grid grid-cols-1 grid-cols-2 grid-cols-3 grid-cols-4 gap-4">
          <ProductCard
            v-for="product in matches"
            :key="product.id"
            :product="product"
            @click="goToProduct(product.id)"
          />
        </div>
      </div>
    </div>
  </div>
</template>
