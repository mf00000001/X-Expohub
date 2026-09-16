<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ProcurementCard from '@/components/ProcurementCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { procurementApi, type Procurement } from '@/api/procurement'
import { productApi, type ProductItem, CATEGORY_PARENT_GROUPS } from '@/api/product'
import { validateInput } from '@/utils/validate'
import http from '@/api/index'

const router = useRouter()
const procurements = ref<Procurement[]>([])
const loading = ref(true)
const error = ref('')
const matchingId = ref<number | null>(null)
const actionMsg = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const myProducts = ref<ProductItem[]>([])
const myCategories = ref<Set<string>>(new Set())
const selectedCategory = ref('')
const allCategories = ref<string[]>([])
// 匹配工作流：每条需求的实时匹配度评分（服务端多阶段打分）
const matchScores = ref<Record<number, { match_score: number; match_level: string; reasons: string[] }>>({})
const sortByMatch = ref(false)

function scoreOf(p: Procurement): { match_score: number; match_level: string; reasons: string[] } {
  return matchScores.value[p.id] || { match_score: 0, match_level: 'low', reasons: [] }
}

const displayProcurements = computed(() => {
  const list = [...procurements.value]
  if (sortByMatch.value) {
    list.sort((a, b) => scoreOf(b).match_score - scoreOf(a).match_score)
  }
  return list
})

function scoreTagClass(level: string): string {
  if (level === 'high') return 'tag-success'
  if (level === 'medium') return 'tag-info'
  return 'tag-warning'
}

async function fetchMatchScores() {
  const ids = procurements.value.map((p) => p.id)
  if (!ids.length) {
    matchScores.value = {}
    return
  }
  try {
    const res: any = await http.get('/recommendations/score-procurements', { params: { ids: ids.join(',') } })
    matchScores.value = res?.data || {}
  } catch {
    matchScores.value = {}  // 打分失败不阻塞列表（徽章隐藏）
  }
}

async function fetchProcurements() {
  loading.value = true
  error.value = ''
  try {
    const params: any = {
      page: currentPage.value,
      page_size: 9,
    }
    if (selectedCategory.value) {
      params.category = selectedCategory.value
    }
    const res = await procurementApi.getList(params)
    procurements.value = res.list || res.items || res.results || []
    totalPages.value = res.total_pages || Math.ceil((res.total || 0) / 9) || 1
    fetchMatchScores()  // 异步补匹配度徽章（不阻塞列表渲染）
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载采购需求失败'
  } finally {
    loading.value = false
  }
}

async function fetchMyProducts() {
  try {
    const res = await productApi.getMyProducts({ status: 'published' })
    const products = res.list || res.items || res.results || []
    myProducts.value = products
    // Extract unique categories
    const cats = new Set<string>()
    const allCats: string[] = []
    products.forEach((p: ProductItem) => {
      if (p.category) {
        cats.add(p.category)
        allCats.push(p.category)
      }
    })
    myCategories.value = cats
    allCategories.value = allCats
  } catch (e: any) {
    console.error('Failed to load my products:', e)
  }
}

function getCategoryMatchLevel(procurement: Procurement): number {
  // Standardized Canton Fair category matching
  // 2 = exact match, 1 = same parent group, 0 = no match
  if (!procurement.category || myCategories.value.size === 0) return 0
  if (myCategories.value.has(procurement.category)) return 2
  // Check if in same parent group
  const procParent = CATEGORY_PARENT_GROUPS[procurement.category]
  if (procParent) {
    for (const myCat of myCategories.value) {
      const myParent = CATEGORY_PARENT_GROUPS[myCat]
      if (myParent && myParent === procParent) return 1
    }
  }
  return 0
}

function filterByCategory() {
  currentPage.value = 1
  fetchProcurements()
}

onMounted(async () => {
  await fetchMyProducts()
  fetchProcurements()
})

async function handleMatch(procurementId: number) {
  matchingId.value = procurementId
  actionMsg.value = ''
  try {
    const msg = prompt('留言（可选）：') || ''
    if (msg) { const v4 = validateInput(msg); if (!v4.valid) { alert(v4.reason); return } }
    await procurementApi.createMatch(procurementId, { message: msg })
    actionMsg.value = '响应成功！已向采购方发送匹配通知'
  } catch (e: any) {
    actionMsg.value = e?.response?.data?.message || e?.response?.data?.detail || e?.message || '匹配失败，请确认该采购仍为待匹配状态'
  } finally {
    matchingId.value = null
  }
}

function goToDetail(id: number) {
  router.push({ name: 'procurement-detail', params: { id } })
}

function changePage(page: number) {
  currentPage.value = page
  fetchProcurements()
  window.scrollTo(0, 0)
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">采购需求匹配</h1>
        <button class="btn btn-outline btn-sm" @click="router.push('/exhibitor/dashboard')">
          ← 返回工作台
        </button>
      </div>

      <div class="category-filter mb-4" v-if="myCategories.size > 0">
        <span class="text-sm text-secondary mr-2">我的品类匹配：</span>
        <select v-model="selectedCategory" @change="filterByCategory" class="select-sm">
          <option value="">全部品类</option>
          <option v-for="cat in [...myCategories]" :key="cat" :value="cat">
            {{ cat }}（精准匹配）
          </option>
        </select>
        <label class="sort-toggle">
          <input type="checkbox" v-model="sortByMatch" />
          按匹配度排序（本页）
        </label>
        <span class="workflow-badge" title="评分由多阶段匹配工作流本地实时计算，零云依赖">⚡ 匹配工作流实时打分</span>
      </div>

      <div v-if="actionMsg" class="tag tag-green mb-4 p-3" style="display:block;">{{ actionMsg }}</div>

      <div v-if="loading" class="loading-container">
        <div class="spinner"></div>
      </div>

      <div v-else-if="error" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="fetchProcurements">重试</button>
      </div>

      <EmptyState v-else-if="procurements.length === 0" message="暂无可匹配的采购需求" icon="🤝" />

      <div v-else class="grid grid-cols-1 grid-cols-2 grid-cols-3 gap-6">
        <div
          v-for="item in displayProcurements"
          :key="item.id"
          class="card"
        >
          <div style="position:relative;">
            <ProcurementCard
              :procurement="item"
              @click="goToDetail(item.id)"
            />
            <span v-if="scoreOf(item).match_score > 0"
                  class="tag"
                  :class="scoreTagClass(scoreOf(item).match_level)"
                  :title="(scoreOf(item).reasons || []).join('\n')"
                  style="position:absolute;top:8px;right:8px;font-size:11px;z-index:1;">
              {{ scoreOf(item).match_score }}% 匹配
            </span>
            <span v-else-if="getCategoryMatchLevel(item) > 0"
                  class="tag"
                  :class="getCategoryMatchLevel(item) === 2 ? 'tag-success' : 'tag-info'"
                  style="position:absolute;top:8px;right:8px;font-size:11px;z-index:1;">
              {{ getCategoryMatchLevel(item) === 2 ? '精准匹配' : '部分匹配' }}
            </span>
          </div>
          <div class="card-footer">
            <button
              v-if="item.status === 'pending'"
              class="btn btn-primary btn-sm btn-block"
              :disabled="matchingId === item.id"
              @click.stop="handleMatch(item.id)"
            >
              {{ matchingId === item.id ? '响应中...' : '🤝 响应此采购' }}
            </button>
          </div>
        </div>
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

<style scoped>
.category-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}

.select-sm {
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--bg-color);
  color: var(--text-primary);
}
.sort-toggle { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary); cursor: pointer; user-select: none; }
.workflow-badge { font-size: 11px; color: var(--color-text-secondary); background: var(--color-bg-page); border: 1px dashed var(--color-border-lighter); border-radius: 999px; padding: 2px 10px; }
</style>