<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import http from '@/api/index'
import SearchBar from '@/components/SearchBar.vue'
import ProductCard from '@/components/ProductCard.vue'

const router = useRouter()
const route = useRoute()
const query = ref('')
const searching = ref(false)
const activeCat = ref('')
const products = ref<any[]>([])
const exhibitions = ref<any[]>([])
const totalResults = ref(0)
const hasSearched = ref(false)

onMounted(() => {
  const q = route.query.q as string
  const c = route.query.cat as string
  if (c) { activeCat.value = c; doSearch() }
  else if (q) { query.value = q; doSearch() }
})

const categories = [
  '电子及家电','照明','车辆及配件','五金工具','机械','建材','化工产品','能源',
  '日用消费品','礼品','纺织服装','鞋类','家居装饰品','办公箱包及休闲用品','食品',
  '医药及医疗保健','AI/科技','综合服务'
]

async function doSearch() {
  const q = query.value.trim()
  if (!q && !activeCat.value) return
  searching.value = true; hasSearched.value = true
  try {
    // Search products by category and/or keyword
    const params: any = { page_size: 24 }
    if (activeCat.value) params.category = activeCat.value
    if (q) params.search = q
    const [prodRes, exhRes] = await Promise.all([
      http.get('/products', { params }).catch(() => ({ list: [] })),
      http.get('/exhibitions', { params: { search: q || activeCat.value, page_size: 6 } }).catch(() => ({ list: [] })),
    ])
    products.value = (prodRes as any)?.list || (prodRes as any)?.data?.list || []
    exhibitions.value = (exhRes as any)?.list || (exhRes as any)?.data?.list || []
    totalResults.value = products.value.length + exhibitions.value.length
  } catch { products.value = []; exhibitions.value = [] }
  finally { searching.value = false }
}

function selectCat(cat: string) {
  activeCat.value = activeCat.value === cat ? '' : cat
  doSearch()
}

function goProduct(id: number) { router.push('/products/' + id) }
function goExhibition(id: number) { router.push('/exhibitions/' + id) }
</script>

<template>
  <div class="search-page-v2">
    <h2>🔍 探索展品</h2>

    <!-- 搜索栏 -->
    <div class="search-row">
      <SearchBar v-model="query" placeholder="搜索展品名称..." @search="doSearch" />
      <span v-if="activeCat" class="active-cat-tag">{{ activeCat }} <button @click="selectCat(activeCat)">×</button></span>
    </div>

    <!-- 分类标签 -->
    <div class="cat-cloud">
      <button v-for="cat in categories" :key="cat" :class="['cat-chip', { active: activeCat === cat }]" @click="selectCat(cat)">{{ cat }}</button>
    </div>

    <!-- 搜索结果 -->
    <div v-if="hasSearched && totalResults === 0 && !searching" style="text-align:center;padding:40px;color:var(--color-text-secondary)">
      未找到结果，换个关键词或分类试试
    </div>

    <div v-if="products.length > 0" class="result-section">
      <h3>📦 展品 ({{ products.length }})</h3>
      <div class="product-grid">
        <ProductCard v-for="p in products" :key="p.id" :product="p" @click="goProduct(p.id)" />
      </div>
    </div>

    <div v-if="exhibitions.length > 0" class="result-section">
      <h3>🎪 相关展会 ({{ exhibitions.length }})</h3>
      <div class="exh-list">
        <div v-for="e in exhibitions" :key="e.id" class="exh-item" @click="goExhibition(e.id)">
          <span>{{ e.title || e.name }}</span>
          <span class="text-muted">{{ e.location }}</span>
        </div>
      </div>
    </div>

    <!-- 默认引导：选个分类 -->
    <div v-if="!hasSearched" class="browse-hint">
      <p>👆 选一个分类，或输入关键词搜索</p>
    </div>
  </div>
</template>

<style scoped>
.search-page-v2 { max-width:900px; margin:0 auto; padding:24px }
.search-row { display:flex; align-items:center; gap:12px; margin-bottom:16px; flex-wrap:wrap }
.active-cat-tag { padding:4px 10px; background:var(--color-primary); color:#fff; border-radius:16px; font-size:13px; display:inline-flex; align-items:center; gap:4px }
.active-cat-tag button { background:none; border:none; color:#fff; cursor:pointer; font-size:14px }
.cat-cloud { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:24px }
.cat-chip { padding:6px 14px; border:1px solid var(--color-border); border-radius:20px; background:#fff; font-size:13px; cursor:pointer; transition:all 0.15s }
.cat-chip:hover { border-color:var(--color-primary); color:var(--color-primary) }
.cat-chip.active { background:var(--color-primary); color:#fff; border-color:var(--color-primary) }
.result-section { margin-bottom:24px }
.result-section h3 { margin-bottom:12px; font-size:16px }
.product-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px }
.exh-list { display:flex; flex-direction:column; gap:8px }
.exh-item { padding:12px 16px; background:var(--color-bg-card); border-radius:8px; cursor:pointer; display:flex; justify-content:space-between }
.exh-item:hover { background:var(--color-bg-page) }
.browse-hint { text-align:center; padding:60px 20px; color:var(--color-text-secondary) }
.browse-hint p { font-size:16px }
</style>
