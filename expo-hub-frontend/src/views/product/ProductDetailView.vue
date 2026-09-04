<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import ImageGallery from '@/components/ImageGallery.vue'
import { productApi } from '@/api/product'
import { analyticsApi } from '@/api/analytics'
import { useUserStore } from '@/stores/user'
import { useI18n } from '@/composables/useI18n'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { pick } = useI18n()

const product = ref<Record<string,any>|null>(null)
const loading = ref(true)

const name = computed(() => pick(product.value, 'name') || '')
const desc = computed(() => pick(product.value, 'description') || '')
const category = computed(() => product.value?.category || '')
const price = computed(() => product.value?.price)
const unit = computed(() => product.value?.unit || '')
const status = computed(() => product.value?.status || '')
const images = computed(() => {
  const imgs = product.value?.images
  if (Array.isArray(imgs) && imgs.length > 0) return imgs
  return []
})
const exhibitorName = computed(() => product.value?.exhibitor_name || product.value?.exhibitorName || '')
const boothId = computed(() => product.value?.booth_id)
const specs = computed(() => product.value?.specs)

onMounted(async () => {
  try {
    product.value = await productApi.getDetail(Number(route.params.id))
    // 浏览埋点：给展商计 view（后端去重 + 同步展品计数）
    if (product.value?.id) {
      analyticsApi.trackEvent({
        event_type: 'page_view', entity_type: 'product',
        entity_id: product.value.id,
        source_user_id: (product.value as any).exhibitor_id,
      })
    }
  } catch (err) { console.error('Failed to load product:', err) }
  finally { loading.value = false }
})

function goToBooth(id: number) { router.push('/booths/'+id) }
function goBack() { router.back() }

const statusMap: Record<string,string> = { active:'在售', inactive:'下架', draft:'草稿' }
</script>

<template>
<div>

<div class="container page-wrapper" v-if="loading"><LoadingSkeleton :lines="6"/></div>
<div v-else-if="!product" class="container page-wrapper"><p>展品不存在</p></div>
<div v-else class="container page-wrapper">
  <div class="breadcrumb">
    <router-link to="/">首页</router-link><span>/</span>
    <router-link to="/products">展品</router-link><span>/</span>
    <span>{{ name }}</span>
  </div>

  <div class="layout-two-col">
    <!-- Gallery -->
    <div class="card">
      <ImageGallery :images="images" :videoUrl="product?.video_url" />
    </div>

    <!-- Info -->
    <div>
      <div class="card card-body">
        <div class="flex justify-between items-start mb-2">
          <h1 class="product-title">{{ name }}</h1>
          <span class="tag" :class="status==='active'?'tag-success':'tag-warning'">{{ statusMap[status] || status }}</span>
        </div>
        <span class="tag tag-info mb-3" v-if="category">{{ category }}</span>
        <p class="desc-text">{{ desc }}</p>

        <div class="info-grid" v-if="exhibitorName || boothId">
          <div v-if="exhibitorName" class="info-item">
            <span class="info-label">展商</span>
            <span class="info-value">{{ exhibitorName }}</span>
          </div>
          <div v-if="boothId" class="info-item">
            <span class="info-label">展位</span>
            <a class="info-link" @click="goToBooth(boothId)">查看展位 -></a>
          </div>
        </div>

        <!-- Specs table -->
        <div v-if="specs && Object.keys(specs).length > 0" class="specs-section">
          <h4>规格参数</h4>
          <table class="specs-table">
            <tr v-for="(v,k) in specs" :key="k">
              <td>{{ k }}</td><td>{{ v }}</td>
            </tr>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>
</div>
</template>

<style scoped>
.layout-two-col { display:grid; grid-template-columns:1fr 1fr; gap:20px }
.product-title { font-size:24px; font-weight:700; line-height:1.3 }
.price-block { font-size:28px; font-weight:700; color:#dc2626; margin:12px 0 }
.desc-text { line-height:1.8; color:#555; margin-bottom:16px }
.info-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; padding:12px 0; border-top:1px solid #f0f0f0 }
.info-item { display:flex; flex-direction:column }
.info-label { font-size:12px; color:#999 }
.info-value { font-size:14px; font-weight:500 }
.info-link { color:#2563eb; cursor:pointer; font-size:14px }
.specs-section { margin-top:16px; padding-top:16px; border-top:1px solid #f0f0f0 }
.specs-section h4 { font-weight:600; margin-bottom:8px }
.specs-table { width:100%; font-size:13px }
.specs-table td { padding:4px 8px; border-bottom:1px solid #f5f5f5 }
.specs-table td:first-child { color:#888; width:40% }
@media(max-width:768px) { .layout-two-col { grid-template-columns:1fr } }
</style>
