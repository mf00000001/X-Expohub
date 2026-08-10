<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import StatusTag from '@/components/StatusTag.vue'
import ProductCard from '@/components/ProductCard.vue'
import { procurementApi, type Procurement } from '@/api/procurement'
import { productApi, type Product } from '@/api/product'
import { useRouter } from 'vue-router'
import http from '@/api/index'
import { validateInput } from '@/utils/validate'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
async function bidOnProcurement() {
  if (!userStore.isLoggedIn) { alert("请先登录"); router.push("/login"); return }
  const msg = prompt("留言（可选）：") || ""
  if (msg) { const v2 = validateInput(msg); if (!v2.valid) { alert(v2.reason); return } }
  try {
    await http.post("/procurements/"+route.params.id+"/matches", {message: msg})
    alert("应标成功！买家已收到通知")
  } catch(e: any) { alert(e?.response?.data?.message||"应标失败，请确认该采购仍为待匹配状态") }
}

const procurement = ref<Procurement | null>(null)
const matches = ref<Product[]>([])
const recommendations = ref<any[]>([])
const recsLoading = ref(false)
const loading = ref(true)

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const [procRes, matchRes] = await Promise.all([
      procurementApi.getDetail(id),
      procurementApi.getMatches(id).catch(() => ({ matches: [] })),
    ])
    procurement.value = procRes
    matches.value = matchRes.matches || matchRes.items || matchRes.results || []
  } catch (err) {
    console.error('Failed to load procurement:', err)
  } finally {
    loading.value = false
  }
  // Fetch recommendations separately (non-blocking)
  fetchRecommendations()
})

function goToProduct(id: number) {
  router.push({ name: 'product-detail', params: { id } })
}

async function fetchRecommendations() {
  if (!procurement.value) return
  recsLoading.value = true
  try {
    const data = await procurementApi.getRecommendations(procurement.value.id)
    recommendations.value = data || []
  } catch (err) {
    console.error('Failed to load recommendations:', err)
  } finally {
    recsLoading.value = false
  }
}
</script>

<template>
  <div>
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

      <!-- Recommended Products -->
      <div class="mt-6" v-if="recommendations.length > 0">
        <h2 class="text-xl font-bold mb-4">推荐展品</h2>
        <div class="grid grid-cols-1 grid-cols-2 grid-cols-3 grid-cols-4 gap-4">
          <div v-for="item in recommendations" :key="item.id" class="recommendation-item">
            <ProductCard
              :product="item"
              @click="goToProduct(item.id)"
            />
            <div class="match-badge" v-if="item.match_score">
              <span class="match-score">{{ item.match_score }}% 匹配</span>
              <span class="match-reasons" v-if="item.match_reasons && item.match_reasons.length">
                {{ item.match_reasons.join(' / ') }}
              </span>
            </div>
          </div>
        </div>
      </div>
      <div class="mt-6" v-else-if="recsLoading">
        <p class="text-secondary text-sm">正在加载推荐展品...</p>
      </div>
    </div>
  </div>
</template>


<style scoped>
.recommendation-item {
  position: relative;
}

.match-badge {
  margin-top: 4px;
  padding: 2px 8px;
  font-size: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.match-score {
  background: var(--primary);
  color: #fff;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
  font-size: 11px;
}

.match-reasons {
  color: var(--text-secondary);
  font-size: 11px;
}
</style>