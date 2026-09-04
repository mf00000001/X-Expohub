<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useI18n } from '@/composables/useI18n'
import { useUserStore } from '@/stores/user'
import { messageApi } from '@/api/message'
import http from '@/api/index'

const route = useRoute()
const router = useRouter()
const { t, pick } = useI18n()
const userStore = useUserStore()

const loading = ref(true)
const profile = ref<any>(null)
const activeTab = ref<string>('products')
const contacting = ref(false)

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const res = await http.get('/exhibitors/' + id + '/profile')
    profile.value = res
  } catch (err) {
    console.error('Failed to load exhibitor profile:', err)
  } finally {
    loading.value = false
  }
})

// 发起会话：先复用与该用户的现有会话，没有则发首条消息自动建会话（后端 POST /messages 语义），
// 成功后携带真实 conversation_id 跳转（旧实现把 user_id 当会话 id 跳，会进错会话）
async function handleContact() {
  if (!userStore.isLoggedIn) {
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  const uid = profile.value?.company?.id
  if (!uid || contacting.value) return
  contacting.value = true
  try {
    const conv: any = await messageApi.startConversation(uid)
    const cid = conv?.id ?? conv?.conversation_id
    if (!cid) throw new Error('no conversation id')
    router.push('/messages/' + cid)
  } catch (e: any) {
    console.error('Failed to start conversation:', e)
    alert(e?.response?.data?.message || '发起会话失败，请稍后再试')
  } finally {
    contacting.value = false
  }
}

function goToProduct(id: number) {
  router.push({ name: 'product-detail', params: { id } })
}

function goToBooth(id: number) {
  router.push({ name: 'booth-detail', params: { id } })
}
</script>

<template>
  <div>
        <div class="container page-wrapper" v-if="loading">
      <LoadingSkeleton :lines="8" />
    </div>
    <div v-else-if="!profile" class="container page-wrapper">
      <p class="text-center text-secondary">Exhibitor not found</p>
    </div>
    <div v-else class="container page-wrapper">
      <div class="breadcrumb">
        <router-link to="/">{{ t('home') }}</router-link>
        <span>/</span>
        <span>{{ pick(profile.company, 'company') || profile.company.username }}</span>
      </div>

      <div class="card company-banner">
        <div class="banner-cover">
          <span class="banner-avatar">{{ (profile.company.company || profile.company.username || '?').charAt(0).toUpperCase() }}</span>
        </div>
        <div class="card-body">
          <div class="flex justify-between items-start" style="flex-wrap:wrap;gap:12px">
            <div>
              <h1 class="text-2xl font-bold">{{ profile.company.company || profile.company.company_name || profile.company.username }}</h1>
              <p class="text-secondary mt-1" v-if="profile.company.position">{{ profile.company.position }}</p>
            </div>
            <div class="flex gap-2">
              <StatusTag v-if="profile.company.organizer_status" :status="profile.company.organizer_status" />
              <span class="tag tag-info">{{ profile.company.role }}</span>
            </div>
          </div>
          <p class="text-sm text-secondary mt-3" v-if="profile.company.bio" style="line-height:1.6">{{ profile.company.bio }}</p>
        </div>
      </div>

      <div class="stats-row mt-4">
        <div class="stat-item">
          <span class="stat-number">{{ profile.stats.total_products }}</span>
          <span class="stat-label">{{ t('totalProducts') }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-number">{{ profile.stats.total_booths }}</span>
          <span class="stat-label">{{ t('totalBooths') }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-number">{{ profile.stats.match_count }}</span>
          <span class="stat-label">{{ t('matchCount') }}</span>
        </div>
      </div>

      <div class="tabs mt-6">
        <button :class="['tab-btn', { active: activeTab === 'products' }]" @click="activeTab = 'products'">{{ t('productList') }}</button>
        <button :class="['tab-btn', { active: activeTab === 'booths' }]" @click="activeTab = 'booths'">{{ t('booths') }}</button>
        <button :class="['tab-btn', { active: activeTab === 'info' }]" @click="activeTab = 'info'">{{ t('companyInfo') }}</button>
      </div>

      <div v-if="activeTab === 'products'" class="mt-4">
        <div v-if="profile.products.length === 0" class="text-center text-secondary p-6">{{ t('noData') }}</div>
        <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-4">
          <div v-for="product in profile.products" :key="product.id" class="card card-body cursor-pointer" @click="goToProduct(product.id)">
            <div v-if="product.images && product.images.length" class="product-thumb">
              <img :src="product.images[0]" :alt="pick(product, 'name')" />
            </div>
            <h4 class="font-semibold text-truncate">{{ pick(product, 'name') }}</h4>
            <p class="text-xs text-secondary text-truncate mt-1" v-if="pick(product, 'description')">{{ pick(product, 'description') }}</p>
            <div class="flex justify-between items-center mt-2">
              <span class="tag tag-sm tag-primary" v-if="product.category">{{ product.category }}</span>
              <span class="font-semibold text-sm" v-if="product.price">&yen;{{ product.price }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'booths'" class="mt-4">
        <div v-if="profile.booths.length === 0" class="text-center text-secondary p-6">{{ t('noData') }}</div>
        <div v-else class="grid grid-cols-1 grid-cols-2 gap-4">
          <div v-for="booth in profile.booths" :key="booth.id" class="card card-body cursor-pointer" @click="goToBooth(booth.id)">
            <div class="flex justify-between items-start">
              <div>
                <span class="font-bold text-lg">{{ booth.booth_number }}</span>
                <span class="text-xs text-secondary ml-2" v-if="booth.size">{{ booth.size }}</span>
              </div>
              <StatusTag :status="booth.status" />
            </div>
            <p class="text-sm text-secondary mt-1" v-if="booth.location_area">{{ booth.location_area }}</p>
            <p class="text-sm font-semibold mt-1" v-if="booth.price">&yen;{{ booth.price }}</p>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'info'" class="mt-4">
        <div class="card card-body">
          <table class="info-table">
            <tr><td class="info-label">{{ t('company') }}</td><td>{{ profile.company.company_name || profile.company.company || '-' }}</td></tr>
            <tr><td class="info-label">{{ t('position') }}</td><td>{{ profile.company.position || '-' }}</td></tr>
            <tr><td class="info-label">{{ t('bio') }}</td><td>{{ profile.company.bio || '-' }}</td></tr>
            <tr><td class="info-label">{{ t('status') }}</td><td><StatusTag :status="profile.company.organizer_status || 'active'" /></td></tr>
          </table>
        </div>
      </div>

      <div class="text-center mt-6">
        <button class="btn btn-primary btn-lg" @click="handleContact" :disabled="contacting">
          {{ contacting ? t('startingConversation') || '发起会话中…' : t('startConversation') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.company-banner { overflow: visible; }
.banner-cover {
  height: 120px;
  background: linear-gradient(135deg, #1a56db 0%, #4f46e5 100%);
  display: flex; align-items: center; justify-content: center;
}
.banner-avatar {
  width: 80px; height: 80px; border-radius: 50%;
  background: rgba(255,255,255,0.25); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 36px; font-weight: 700;
  border: 3px solid #fff;
}
.card-body { padding-top: 48px; }
.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.stat-item {
  background: var(--color-white); border: 1px solid var(--color-border);
  border-radius: var(--radius-md); padding: 16px; text-align: center;
}
.stat-number { display: block; font-size: 28px; font-weight: 800; color: var(--color-primary); }
.stat-label { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }
.tabs { display: flex; border-bottom: 2px solid var(--color-border); gap: 0; }
.tab-btn {
  padding: 10px 24px; border: none; background: none; font-size: 15px; font-weight: 500;
  color: var(--color-text-secondary); cursor: pointer; border-bottom: 2px solid transparent;
  margin-bottom: -2px; transition: all 0.15s;
}
.tab-btn:hover { color: var(--color-text); }
.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }
.product-thumb { height: 120px; overflow: hidden; margin-bottom: 8px; border-radius: 6px; }
.product-thumb img { width: 100%; height: 100%; object-fit: cover; }
.info-table { width: 100%; }
.info-table td { padding: 10px 12px; font-size: 14px; border-bottom: 1px solid var(--color-border-light); }
.info-label { width: 80px; color: var(--color-text-secondary); font-weight: 500; }
.ml-2 { margin-left: 8px; }
</style>
