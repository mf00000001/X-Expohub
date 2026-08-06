<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import ProductCard from '@/components/ProductCard.vue'
import { exhibitionApi } from '@/api/exhibition'
import { boothApi } from '@/api/booth'
import { productApi } from '@/api/product'
import { registrationApi } from '@/api/registration'
import { useUserStore } from '@/stores/user'
import { useI18n } from '@/composables/useI18n'
import http from '@/api/index'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { pick } = useI18n()

const exhibition = ref<Record<string,any>|null>(null)
const booths = ref<any[]>([])
const products = ref<any[]>([])
const procurements = ref<any[]>([])
const loading = ref(true)
const registered = ref(false)
const tab = ref<'booths'|'products'|'procurements'>('booths')

const title = computed(() => pick(exhibition.value, 'title') || exhibition.value?.name || '')
const cover = computed(() => exhibition.value?.cover_image || exhibition.value?.cover_url || '')
const startDate = computed(() => exhibition.value?.start_date || exhibition.value?.startDate || '')
const endDate = computed(() => exhibition.value?.end_date || exhibition.value?.endDate || '')
const location = computed(() => exhibition.value?.location || exhibition.value?.venue || '')
const orgName = computed(() => exhibition.value?.organizer_name || exhibition.value?.organizerName || '')
const orgId = computed(() => exhibition.value?.organizer_id)
const desc = computed(() => pick(exhibition.value, 'description') || '')
const status = computed(() => exhibition.value?.status || '')
const boothCount = computed(() => booths.value.length)

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const [expRes, boothRes, prodRes, procRes] = await Promise.all([
      exhibitionApi.getDetail(id),
      boothApi.getList({ exhibition_id: id, page_size: 50 }),
      productApi.getList({ exhibition_id: id }),
      http.get('/procurements', { params: { exhibition_id: id, page_size: 20 } }).catch(() => ({})),
    ])
    exhibition.value = expRes
    booths.value = boothRes.list || boothRes.items || []
    products.value = prodRes.list || prodRes.items || []
    procurements.value = (procRes as any)?.data?.list || (procRes as any)?.list || []
  } catch (err) {
    console.error('Failed to load exhibition:', err)
  } finally {
    loading.value = false
  }
})

async function handleRegister() {
  if (!userStore.isLoggedIn) { router.push('/login'); return }
  try {
    await registrationApi.register({ exhibition_id: Number(route.params.id) })
    registered.value = true
    showToast('报名成功!')
  } catch (err: any) { showToast('报名失败', 'error') }
}

function showToast(msg: string, type='success') {
  const t = document.createElement('div')
  t.className = 'toast toast-'+type; t.textContent = msg
  document.body.appendChild(t); setTimeout(() => t.remove(), 3000)
}

function goToBooth(id: number) { router.push('/booths/'+id) }
async function applyBooth(bid: number) {
  if (!userStore.isLoggedIn) { router.push('/login'); return }
  try { await http.post('/booths/'+bid+'/apply'); alert('申请已提交！')
  } catch(e: any) { alert(e?.response?.data?.message||'申请失败') }
}
function goToProduct(id: number) { router.push('/products/'+id) }
function canRegister(s: string) { return s === 'published' || s === 'ongoing' }

const statusMap: Record<string,string> = {
  draft:'草稿', pending:'待审核', published:'已发布',
  ongoing:'进行中', ended:'已结束', cancelled:'已取消'
}
const statusClass = computed(() => {
  if (status.value==='published'||status.value==='ongoing') return 'tag-success'
  if (status.value==='pending') return 'tag-warning'
  return 'tag-info'
})
</script>

<template>
<div>
<div class="container page-wrapper" v-if="loading"><LoadingSkeleton :lines="8"/></div>
<div v-else-if="!exhibition" class="container page-wrapper"><p>展会不存在</p></div>
<div v-else class="container page-wrapper">
  <div class="breadcrumb">
    <router-link to="/">首页</router-link><span>/</span>
    <router-link to="/exhibitions">展会</router-link><span>/</span>
    <span>{{ title }}</span>
  </div>

  <!-- Hero -->
  <div class="detail-hero" v-if="cover">
    <img :src="cover" :alt="title" />
    <div class="hero-overlay">
      <span class="tag" :class="statusClass">{{ statusMap[status] || status }}</span>
      <h1>{{ title }}</h1>
      <div class="hero-meta">
        <span>📅 {{ startDate }} ~ {{ endDate }}</span>
        <span>📍 {{ location }}</span>
        <router-link v-if="orgName && orgId" :to="'/exhibitor/' + orgId" class="organizer-link">👤 {{ orgName }}</router-link>
        <span>🏢 {{ boothCount }} 个展位</span>
      </div>
    </div>
  </div>

  <!-- No cover fallback -->
  <div v-else class="card card-body mb-4">
    <div class="flex justify-between items-start">
      <h1>{{ title }}</h1>
      <span class="tag" :class="statusClass">{{ statusMap[status] || status }}</span>
    </div>
    <div class="meta-row">
      <span>📅 {{ startDate }} ~ {{ endDate }}</span>
      <span>📍 {{ location }}</span>
      <span v-if="orgName">👤 {{ orgName }}</span>
    </div>
  </div>

  <!-- Description -->
  <div class="card card-body mb-4" v-if="desc">
    <h3 class="section-title">📋 展会简介</h3>
    <p class="desc-text">{{ desc }}</p>
    <button v-if="canRegister(status)" class="btn btn-primary btn-lg mt-4" @click="handleRegister">
      {{ registered ? '已报名' : '立即报名参展' }}
    </button>
  </div>

  <!-- Tabs: Booths / Products -->
  <div class="card mb-4">
    <div class="tab-header">
      <button :class="['tab-btn', {active:tab==='booths'}]" @click="tab='booths'">🏢 展位 ({{booths.length}})</button>
      <button :class="['tab-btn', {active:tab==='products'}]" @click="tab='products'">📦 展品 ({{products.length}})</button>
      <button :class="['tab-btn', {active:tab==='procurements'}]" @click="tab='procurements'">📋 采购需求 ({{procurements.length}})</button>
    </div>

    <!-- Booths -->
    <div v-if="tab==='booths'" class="card-body">
      <div v-if="booths.length===0" class="empty-hint">暂无展位</div>
      <div v-else class="booth-grid">
        <div v-for="b in booths" :key="b.id" class="booth-card" @click="goToBooth(b.id)">
          <div class="booth-header">
            <span class="booth-num">{{ b.booth_number }}</span>
            <span class="tag tag-sm" :class="b.status==='occupied'?'tag-success':b.status==='available'?'tag-info':'tag-warning'">
              {{ b.status==='occupied'?'已入驻':b.status==='available'?'可预订':b.status }}
            </span>
          </div>
          <p class="booth-company" v-if="b.company_name">{{ b.company_name }}</p>
            <button v-if="b.status==='available'" class="btn btn-sm btn-primary-outline" @click.stop="applyBooth(b.id)" style="margin-top:6px">申请入驻</button>
          <div class="booth-info">
            <span v-if="b.size">面积: {{ b.size }}</span>
            <span v-if="b.location_area">{{ b.location_area }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Products -->
    <div v-if="tab==='products'" class="card-body">
      <div v-if="products.length===0" class="empty-hint">暂无展品</div>
      <div v-else class="product-grid">
        <ProductCard v-for="p in products" :key="p.id" :product="p" @click="goToProduct(p.id)"/>
      </div>
    </div>

    <!-- Procurements -->
    <div v-if="tab==='procurements'" class="card-body">
      <div v-if="procurements.length===0" class="empty-hint">暂无采购需求</div>
      <div v-else class="proc-list">
        <div v-for="p in procurements" :key="p.id" class="proc-item" @click="router.push('/procurements/'+p.id)">
          <div class="proc-left"><strong>{{ p.title }}</strong><span class="proc-cat">{{ p.category }}</span></div>
          <span class="tag" :class="p.status==='pending'?'tag-warning':'tag-info'">{{ p.status==='pending'?'待匹配':'已匹配' }}</span>
        </div>
      </div>
    </div>
  </div>
</div>
</div>
</template>

<style scoped>
.detail-hero { position:relative; height:320px; overflow:hidden; border-radius:12px; margin-bottom:16px }
.detail-hero img { width:100%; height:100%; object-fit:cover }
.hero-overlay { position:absolute; bottom:0; left:0; right:0; padding:40px 24px 24px; background:linear-gradient(transparent,rgba(0,0,0,0.75)); color:#fff }
.hero-overlay h1 { font-size:28px; font-weight:700; margin:8px 0 }
.hero-meta { display:flex; gap:20px; flex-wrap:wrap; font-size:14px; opacity:0.9 }
.meta-row { display:flex; gap:20px; flex-wrap:wrap; font-size:14px; color:#666; margin-top:8px }
.section-title { font-size:18px; font-weight:600; margin-bottom:12px }
.desc-text { line-height:1.9; color:#555; white-space:pre-wrap }
.tab-header { display:flex; border-bottom:1px solid #e5e7eb }
.tab-btn { flex:1; padding:14px; border:none; background:none; font-size:15px; font-weight:500; cursor:pointer; color:#666; border-bottom:2px solid transparent; transition:all .2s }
.tab-btn.active { color:#2563eb; border-bottom-color:#2563eb; background:#eff6ff }
.booth-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:12px }
.booth-card { padding:16px; border:1px solid #e5e7eb; border-radius:8px; cursor:pointer; transition:all .2s }
.booth-card:hover { border-color:#2563eb; box-shadow:0 2px 8px rgba(37,99,235,0.1) }
.booth-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px }
.booth-num { font-weight:700; font-size:16px; color:#1f2937 }
.booth-company { font-size:14px; color:#2563eb; margin-bottom:6px }
.booth-info { display:flex; gap:12px; font-size:12px; color:#888; flex-wrap:wrap }
.product-grid { display:flex; flex-direction:column; gap:8px }
.empty-hint { text-align:center; padding:40px; color:#999 }
.tag-sm { font-size:11px; padding:2px 6px }
.btn-lg { padding:12px 32px; font-size:16px }
@media(max-width:640px) { .detail-hero { height:200px } .hero-overlay h1 { font-size:20px } }
</style>