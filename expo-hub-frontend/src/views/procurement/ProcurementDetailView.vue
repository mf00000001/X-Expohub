<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import StatusTag from '@/components/StatusTag.vue'
import ProductCard from '@/components/ProductCard.vue'
import { procurementApi, type Procurement, type ProcurementMatch } from '@/api/procurement'
import { aiApi } from '@/api/ai'
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
  if (userStore.userRole !== 'exhibitor') { alert("仅展商可应标"); return }
  const msg = prompt("留言（可选）：") || ""
  if (msg) { const v2 = validateInput(msg); if (!v2.valid) { alert(v2.reason); return } }
  try {
    await http.post("/procurements/"+route.params.id+"/matches", {message: msg})
    alert("应标成功！买家已收到通知")
  } catch(e: any) { alert(e?.response?.data?.message||"应标失败，请确认该采购仍为待匹配状态") }
}

const procurement = ref<Procurement | null>(null)
const matches = ref<ProcurementMatch[]>([])
const recommendations = ref<any[]>([])
const recsLoading = ref(false)
const loading = ref(true)
const aiNote = ref('')
const aiLoading = ref(false)
const aiProvider = ref('')

function fmtMatchTime(s?: string) {
  return s ? String(s).slice(0, 16).replace('T', ' ') : ''
}

// 买家接受应标：后端置本单 is_accepted=True 并完成采购（其余应标自动落选）
async function acceptMatch(m: ProcurementMatch) {
  if (!procurement.value) return
  if (!confirm('确定接受「' + (m.exhibitor_company || m.exhibitor_username || '该展商') + '」的应标？接受后采购将完成，其余应标自动落选')) return
  try {
    const res: any = await procurementApi.acceptMatch(procurement.value.id, m.id)
    if (res?.procurement?.status) procurement.value.status = res.procurement.status
    matches.value = matches.value.map((x) => ({ ...x, is_accepted: x.id === m.id }))
    alert('✅ 已接受该应标，采购需求已完结')
  } catch (e: any) {
    alert(e?.response?.data?.message || '操作失败')
  }
}

// 匹配/推荐仅"需求发布者"或 admin 可见"需求发布者"或 admin 可见（后端 403 语义，前端同步门控避免无谓请求）
function canViewPrivate(): boolean {
  if (!procurement.value) return false
  const ownerId = (procurement.value as any).visitor_id ?? (procurement.value as any).purchaser_id
  return userStore.userRole === 'admin' || ownerId === userStore.profile?.id
}

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    procurement.value = await procurementApi.getDetail(id)
    if (userStore.isLoggedIn && canViewPrivate()) {
      const matchRes = await procurementApi.getMatches(id).catch(() => ({ list: [], matches: [], items: [], results: [], total: 0 }))
      matches.value = matchRes.list || matchRes.matches || []
      fetchRecommendations()
    }
  } catch (err) {
    console.error('Failed to load procurement:', err)
  } finally {
    loading.value = false
  }
})

function goToProduct(id: number) {
  router.push({ name: 'product-detail', params: { id } })
}

async function fetchRecommendations() {
  if (!procurement.value || !canViewPrivate()) return
  recsLoading.value = true
  try {
    const data: any = await procurementApi.getRecommendations(procurement.value.id)
    recommendations.value = data?.list || data?.recommendations || (Array.isArray(data) ? data : [])
  } catch (err) {
    // 非致命：静默（后端 403 属权限正常路径）
  } finally {
    recsLoading.value = false
  }
}

// AI 推荐说明：把推荐理由交给人话化（AI 实验室 reason 能力；未配密钥时后端 mock 降级并如实标注）
async function genAiNote() {
  if (!procurement.value || aiLoading.value) return
  aiLoading.value = true
  aiNote.value = ''
  try {
    const top = recommendations.value.slice(0, 3).map((r: any) =>
      `《${r.name}》(展商:${r.exhibitor_name || '未知'};理由:${(r.match_reasons || []).join('、') || '推荐'})`
    ).join('；')
    const prompt = `采购需求「${procurement.value.title}」属于${procurement.value.category || '未分类'}。已推荐以下展品：${top}。请用3-4句话向买家说明这些展品为何值得重点对接，中文、口语化、给出对接建议。`
    const r: any = await aiApi.generate({ capability: 'reason', prompt })
    aiNote.value = r?.content || '（无返回内容）'
    aiProvider.value = r?.provider || ''
  } catch (e: any) {
    aiNote.value = 'AI 生成失败：' + (e?.response?.data?.message || '请稍后再试')
  } finally {
    aiLoading.value = false
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
            <div><span class="text-secondary">采购方：</span>{{ (procurement as any).visitor_username || '匿名买家' }}</div>
            <div v-if="procurement.category"><span class="text-secondary">分类：</span>{{ procurement.category }}</div>
            <div v-if="procurement.deadline"><span class="text-secondary">截止日期：</span>{{ procurement.deadline }}</div>
            <div v-if="procurement.status"><span class="text-secondary">状态：</span>{{ {pending:'待匹配',matched:'已匹配',cancelled:'已取消'}[procurement.status] || procurement.status }}</div>
          </div>
          <p class="text-secondary" style="line-height:1.8;white-space:pre-wrap;">{{ procurement.description }}</p>
        </div>
      </div>

      <!-- V3.4: 未登录提示 -->
      <div v-if="!userStore.isLoggedIn" class="mt-6 card card-body text-center">
        <p class="text-secondary text-sm">🔒 登录后可查看匹配展商与推荐展品、参与应标</p>
      </div>

      <!-- Matched Products -->
      <div v-if="userStore.isLoggedIn && procurement && !canViewPrivate()" class="tag tag-info" style="margin-top:12px">匹配与推荐仅需求发布者可查看</div>
<div class="mt-6" v-if="matches.length > 0">
        <h2 class="text-xl font-bold mb-4">应标展商（{{ matches.length }}）</h2>
        <div class="flex flex-col gap-2">
          <div v-for="m in matches" :key="m.id" class="card card-body">
            <div class="flex justify-between items-center">
              <strong>{{ m.exhibitor_company || m.exhibitor_username || ('展商#'+m.exhibitor_id) }}</strong>
              <span v-if="m.quoted_price" class="tag tag-info">报价 ¥{{ m.quoted_price }}</span>
              <span v-else class="tag tag-warning">待议价</span>
            </div>
            <p v-if="m.message" class="text-sm text-secondary mt-1">{{ m.message }}</p>
            <p class="text-xs text-secondary mt-1">{{ fmtMatchTime(m.created_at) }}</p>
            <div class="mt-2" v-if="procurement && (procurement.status === 'pending' || procurement.status === 'matched')">
              <button v-if="!m.is_accepted" class="btn btn-sm btn-success" @click="acceptMatch(m)">🤝 接受此应标</button>
              <span v-else class="tag tag-success">✅ 已接受</span>
            </div>
            <div class="mt-2" v-else-if="procurement && procurement.status === 'completed'">
              <span v-if="m.is_accepted" class="tag tag-success">✅ 已成交</span>
              <span v-else class="tag tag-info">未选中</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Recommended Products -->
      <div class="mt-6" v-if="recommendations.length > 0">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h2 class="text-xl font-bold" style="margin:0">推荐展品</h2>
          <button class="btn btn-sm btn-outline" :disabled="aiLoading" @click="genAiNote">{{ aiLoading ? '生成中...' : '✨ AI 生成推荐说明' }}</button>
        </div>
        <div v-if="aiNote" class="card card-body mb-4" style="border-left:3px solid #4f6ef7">
          <p style="margin:0;line-height:1.8;white-space:pre-wrap">{{ aiNote }}</p>
          <p v-if="aiProvider" style="margin:8px 0 0;font-size:12px;color:var(--color-text-placeholder)">via {{ aiProvider }}{{ aiProvider === 'mock' ? '（未配置真实模型，内容为示例占位）' : '' }}</p>
        </div>
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