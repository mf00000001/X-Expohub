<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
    // 状态已变为 matched：刷新详情（按钮随状态隐藏）
    procurement.value = await procurementApi.getDetail(Number(route.params.id))
  } catch(e: any) { alert(e?.response?.data?.message||"应标失败，请确认该采购仍为待匹配状态") }
}

// 展商视角：与当前用户展品的匹配度（本地匹配工作流即时打分，零等待）
const myMatch = ref<any>(null)
const myMatchLoading = ref(false)
async function fetchMyMatch() {
  if (userStore.userRole !== 'exhibitor' || !procurement.value) return
  myMatchLoading.value = true
  try {
    const res: any = await http.get('/recommendations/score-procurements', { params: { ids: String(procurement.value.id) } })
    const dict = (res && typeof res === 'object' && res.data && typeof res.data === 'object') ? res.data : res
    myMatch.value = dict?.[String(procurement.value.id)] || null
  } catch { myMatch.value = null } finally { myMatchLoading.value = false }
}

const STATUS_LABEL: Record<string, string> = { pending: '待匹配', open: '进行中', published: '已发布', matched: '已匹配', closed: '已截止', completed: '已完成', cancelled: '已取消' }

const procurement = ref<Procurement | null>(null)
const matches = ref<ProcurementMatch[]>([])
const recommendations = ref<any[]>([])
const recsLoading = ref(false)
const recPipeline = ref<any>(null)
const loading = ref(true)
const aiNote = ref('')
const aiLoading = ref(false)
const aiProvider = ref('')

// 本地解读（匹配工作流即时生成，零云依赖、零等待）
const localNote = computed(() => {
  if (!recommendations.value.length) return ''
  const top = recommendations.value.slice(0, 3)
  const t = top[0]
  const rs = (t?.match_reasons || t?.reasons || []).join('、') || '综合匹配'
  const recalled = recPipeline.value?.recalled
  const n = recommendations.value.length
  return `匹配工作流${recalled ? `从 ${recalled} 个候选中` : ''}筛选出 ${n} 个展品；最高匹配为《${t?.name ?? '-'}》（${t?.match_score ?? '-'}%）：${rs}。建议优先对接 Top${Math.min(3, n)} 展商。`
})

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
    // 展商视角：给这条需求算"与你展品的匹配度"
    fetchMyMatch()
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
    recPipeline.value = data?.pipeline || null
  } catch (err) {
    // 非致命：静默（后端 403 属权限正常路径）
  } finally {
    recsLoading.value = false
  }
}

// AI 推荐说明：把推荐理由交给人话化（AI 实验室 reason 能力；未配密钥时后端 mock 降级并如实标注）。
// 匹配主链路不依赖云端 —— AI 失败/超时时自动降级为本地工作流解读。
async function genAiNote() {
  if (!procurement.value || aiLoading.value) return
  aiLoading.value = true
  aiNote.value = ''
  try {
    const top = recommendations.value.slice(0, 3).map((r: any) =>
      `《${r.name}》(展商:${r.exhibitor_name || '未知'};理由:${(r.match_reasons || r.reasons || []).join('、') || '推荐'})`
    ).join('；')
    const prompt = `采购需求「${procurement.value.title}」属于${procurement.value.category || '未分类'}。已推荐以下展品：${top}。请用3-4句话向买家说明这些展品为何值得重点对接，中文、口语化、给出对接建议。`
    const r: any = await aiApi.generate({ capability: 'reason', prompt })
    aiNote.value = r?.content || '（无返回内容）'
    aiProvider.value = r?.provider || ''
  } catch (e: any) {
    // 云端 AI 不可用 → 降级为本地工作流解读（主链路零依赖）
    aiNote.value = `（AI 服务暂不可用，以下为本地匹配工作流解读）\n${localNote.value}`
    aiProvider.value = 'local-fallback'
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

      <!-- 展商视角：与我的匹配度 + 应标（本地匹配工作流即时打分） -->
      <div v-if="userStore.userRole === 'exhibitor' && procurement && !canViewPrivate()" class="card card-body mt-4" style="border-left:3px solid var(--primary)">
        <div class="flex justify-between items-center" style="flex-wrap:wrap;gap:10px">
          <div>
            <span class="text-secondary text-sm">🎯 与你展品的匹配度：</span>
            <template v-if="myMatch && (myMatch.match_score || 0) > 0">
              <span class="match-score" :class="myMatch.match_level === 'high' ? 'score-high' : (myMatch.match_level === 'medium' ? 'score-medium' : 'score-low')">{{ myMatch.match_score }}%</span>
            </template>
            <span v-else-if="myMatchLoading" class="text-sm text-secondary">计算中…</span>
            <span v-else class="text-sm text-secondary">暂无匹配（与你的展品品类/关键词关联较低）</span>
            <div v-if="myMatch && myMatch.reasons && myMatch.reasons.length" class="match-reasons" style="margin-top:6px">
              {{ myMatch.reasons.join(' / ') }}
            </div>
          </div>
          <div>
            <button v-if="procurement.status === 'pending' && !canViewPrivate()" class="btn btn-primary" @click="bidOnProcurement">🤝 立即应标</button>
            <span v-else-if="!canViewPrivate()" class="tag tag-info">当前状态（{{ STATUS_LABEL[procurement.status] || procurement.status }}）暂不可应标</span>
          </div>
        </div>
        <p style="margin:8px 0 0;font-size:11px;color:var(--color-text-placeholder)">匹配度由本地匹配工作流按你的展品品类与关键词即时计算（零等待、零云依赖）</p>
      </div>

      <!-- V3.4: 未登录提示 -->
      <div v-if="!userStore.isLoggedIn" class="mt-6 card card-body text-center">
        <p class="text-secondary text-sm">🔒 登录后展商可查看与该需求的匹配度并应标；需求发布者可查看应标与推荐展品</p>
      </div>

      <!-- Matched Products -->
      <div v-if="userStore.isLoggedIn && procurement && !canViewPrivate() && userStore.userRole !== 'exhibitor'" class="tag tag-info" style="margin-top:12px">🔒 应标展商与推荐展品仅需求发布者可查看</div>
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

      <!-- Recommended Products（本地匹配工作流） -->
      <div class="mt-6" v-if="recommendations.length > 0">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <h2 class="text-xl font-bold" style="margin:0">推荐展品</h2>
          <button class="btn btn-sm btn-outline" :disabled="aiLoading" @click="genAiNote">{{ aiLoading ? 'AI 生成中(约10–30秒,请耐心等待)...' : '✨ AI 生成推荐说明' }}</button>
        </div>
        <p class="pipeline-hint" v-if="recPipeline">
          ⚡ 本地匹配工作流（零云依赖）· 候选 {{ recPipeline.recalled ?? '—' }} → 打分 {{ recPipeline.scored ?? '—' }} → 展示 {{ recPipeline.returned ?? recommendations.length }} · 用时 {{ recPipeline.total_ms ?? '—' }}ms
        </p>
        <div v-if="aiNote" class="card card-body mb-4" style="border-left:3px solid #4f6ef7">
          <p style="margin:0;line-height:1.8;white-space:pre-wrap">{{ aiNote }}</p>
          <p v-if="aiProvider && aiProvider !== 'local-fallback'" style="margin:8px 0 0;font-size:12px;color:var(--color-text-placeholder)">via {{ aiProvider }}{{ aiProvider === 'mock' ? '（未配置真实模型，内容为示例占位）' : '' }}</p>
          <p v-else style="margin:8px 0 0;font-size:12px;color:var(--color-text-placeholder)">via 本地匹配工作流（零云依赖）</p>
        </div>
        <div v-else class="card card-body mb-4" style="border-left:3px solid #10b981">
          <p style="margin:0;line-height:1.8">⚡ <strong>本地解读</strong>：{{ localNote }}</p>
          <p style="margin:8px 0 0;font-size:12px;color:var(--color-text-placeholder)">由匹配工作流即时生成（零等待、零云依赖）· 需要更口语化的版本可点右上「AI 生成推荐说明」</p>
        </div>
        <div class="grid grid-cols-1 grid-cols-2 grid-cols-3 grid-cols-4 gap-4">
          <div v-for="item in recommendations" :key="item.id" class="recommendation-item">
            <ProductCard
              :product="item"
              @click="goToProduct(item.id)"
            />
            <div class="match-badge" v-if="item.match_score">
              <span class="match-score" :class="item.match_level === 'high' ? 'score-high' : (item.match_level === 'medium' ? 'score-medium' : 'score-low')">{{ item.match_score }}% 匹配</span>
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
.match-score.score-high { background: #16a34a; }
.match-score.score-medium { background: #2563eb; }
.match-score.score-low { background: #9ca3af; }

.pipeline-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.match-reasons {
  color: var(--text-secondary);
  font-size: 11px;
}
</style>