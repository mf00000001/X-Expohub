<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { microBoothApi, type MicroBooth } from '@/api/micro-booth'
import { exhibitionApi } from '@/api/exhibition'
import http from '@/api/index'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const route = useRoute()
const booths = ref<MicroBooth[]>([])
const detail = ref<any>(null)
const loading = ref(true)
const keyword = ref('')
const activeDomain = ref('')
const isDetail = ref(false)

// V3.4: 展会筛选(微展位按展会归类)
const exhibitions = ref<any[]>([])
const activeExhibition = ref<number | null>(null)
async function loadExhibitions() {
  try {
    const res: any = await exhibitionApi.getList({ page_size: 10 })
    const list = (res as any).list || (res as any).items || []
    // 仅正式发布的展会(排除草稿/测试)
    exhibitions.value = list.filter((e: any) => e.status === 'published' || e.status === 'ongoing')
  } catch {
    exhibitions.value = []
  }
}
function selectExhibition(id: number | null) {
  activeExhibition.value = id
  fetchList()
}

const domains = [
  '电子及家电','照明','车辆及配件','五金工具','机械','建材','化工产品','能源',
  '日用消费品','礼品','纺织服装','鞋类','家居装饰品','办公箱包及休闲用品','食品',
  '医药及医疗保健','AI/科技','综合服务'
]

onMounted(async () => {
  const id = route.params.id
  if (id) {
    isDetail.value = true
    await fetchDetail(Number(id))
  } else {
    await loadExhibitions()
    await fetchList()
  }
})

watch(() => route.params.id, async (id) => {
  if (id) { isDetail.value = true; await fetchDetail(Number(id)) }
  else { isDetail.value = false; await fetchList() }
})

async function fetchList() {
  loading.value = true
  try {
    const params: any = { page_size: 50, sort: 'tier' }
    if (activeDomain.value) params.industry_domain = activeDomain.value
    if (activeExhibition.value) params.exhibition_id = activeExhibition.value
    if (keyword.value) { params.search = keyword.value; activeDomain.value = '' }
    const res: any = await microBoothApi.getList(params)
    booths.value = (res?.list || res?.data?.list || [])
  } catch { booths.value = [] }
  finally { loading.value = false }
}

async function fetchDetail(id: number) {
  loading.value = true
  try {
    const res: any = await microBoothApi.getDetail(id)
    detail.value = res?.data || res
    http.post('/analytics/event', { event_type: 'page_view', entity_type: 'micro_booth', entity_id: id, source_user_id: detail.value?.booth?.exhibitor_id }).catch(()=>{})
  } catch { detail.value = null }
  finally { loading.value = false }
}

function handleSearch(v: string) { keyword.value = v; fetchList() }
function selectDomain(d: string) {
  activeDomain.value = activeDomain.value === d ? '' : d
  fetchList()
}
function goDetail(id: number) {
  router.push('/micro-booths/'+id)
}
function goBack() { router.push('/micro-booths') }

const showApptForm = ref(false); const apptExhId = ref(0); const apptSlot = ref('全天')
async function makeAppointment() {
  if (!localStorage.getItem('access_token')) { alert('请先登录'); return }
  if (!detail.value?.booth) return
  showApptForm.value = !showApptForm.value
}
async function confirmAppt() {
  if (!apptExhId.value) { alert('请选择展会'); return }
  try {
    await http.post('/appointments', {exhibitor_id: detail.value.booth.exhibitor_id, exhibition_id: apptExhId.value, time_slot: apptSlot.value})
    alert('预约成功！展会现场见')
    showApptForm.value = false
  } catch(e: any) { alert(e?.response?.data?.message || '预约失败') }
}
const mbFaved = ref(false)
function toggleMbFav() {
  if (!localStorage.getItem('access_token')) { alert('请先登录'); return }
  http.post('/favorites/toggle', {entity_type:'micro_booth',entity_id:detail.value?.booth?.id}).then((r:any)=>{ mbFaved.value = r?.data?.favorited || r?.favorited || false }).catch(()=>{})
}
const tierBadge: Record<string,string> = { free:'🆓 免费', regular:'⭐ VIP', flagship:'👑 旗舰' }
</script>

<template>
  <!-- Detail Mode -->
  <div class="page-container" v-if="isDetail">
    <div v-if="loading"><LoadingSkeleton :lines="6"/></div>
    <div v-else-if="!detail" class="card" style="text-align:center;padding:40px">微展位不存在</div>
    <div v-else>
      <button class="btn-back" @click="goBack" style="margin-bottom:16px">← 返回广场</button>

      <div class="detail-card">
        <div class="detail-header">
          <span class="detail-tier">{{ tierBadge[detail.booth?.membership_tier] }}</span>
          <h1>{{ detail.booth?.name }} <button class="fav-btn" @click="toggleMbFav()" title="收藏">{{ mbFaved ? '❤️' : '🤍' }} 收藏</button>
          <button class="appt-btn" @click="makeAppointment()" title="预约见面">🎯 预约展会见面</button></h1>
          <p class="detail-domain" v-if="detail.booth?.industry_domain">{{ detail.booth?.industry_domain }}</p>
        </div>

        <!-- V3.4: 所属展会信息 -->
        <div v-if="detail.booth?.exhibition_info" class="detail-exh" @click="router.push('/exhibitions/' + detail.booth.exhibition_info.id)">
          <div class="deh-title">🏟️ 所属展会</div>
          <div class="deh-name">{{ detail.booth.exhibition_info.title }}</div>
          <div class="deh-meta">
            <span>📅 {{ (detail.booth.exhibition_info.start_date || '').slice(0,10) }} ~ {{ (detail.booth.exhibition_info.end_date || '').slice(0,10) }}</span>
            <span>📍 {{ detail.booth.exhibition_info.location }}</span>
          </div>
          <div class="deh-link">查看展会详情 →</div>
        </div>

        <p class="detail-desc" v-if="detail.booth?.description">{{ detail.booth?.description }}</p>

        <div class="detail-stats">
          <div class="dstat"><strong>{{ detail.booth?.view_count || 0 }}</strong><span>浏览</span></div>
          <div class="dstat"><strong>{{ detail.booth?.search_appearances || 0 }}</strong><span>搜索曝光</span></div>
          <div class="dstat"><strong>{{ detail.booth?.favorite_count || 0 }}</strong><span>收藏</span></div>
          <div class="dstat"><strong>{{ detail.booth?.product_count || 0 }}</strong><span>展品</span></div>
        </div>
        <div v-if="showApptForm" class="appt-form">
          <h4>📅 预约展会见面</h4>
          <select v-model="apptExhId" class="form-input" style="margin:8px 0">
            <option :value="0">选择展会</option>
            <option :value="1">广交会</option>
            <option :value="2">上海进博会</option>
            <option :value="3">深圳高交会</option>
          </select>
          <select v-model="apptSlot" class="form-input" style="margin:8px 0">
            <option value="上午">上午</option>
            <option value="下午">下午</option>
            <option value="全天">全天</option>
          </select>
          <button class="btn btn-primary btn-sm" @click="confirmAppt">确认预约</button>
          <button class="btn btn-sm btn-default" @click="showApptForm=false" style="margin-left:8px">取消</button>
        </div>

        <!-- Products -->
        <div class="detail-products" v-if="detail.products?.length > 0">
          <h3>📦 展品列表 ({{ detail.products.length }})</h3>
          <div class="dprod-grid">
            <div v-for="p in detail.products" :key="p.id" class="dprod-card" @click="router.push('/products/'+p.id)">
              <div class="dprod-img">📦</div>
              <div class="dprod-info">
                <strong>{{ p.name }}</strong>
                <span class="dprod-cat">{{ p.category }}</span>
                <span class="dprod-desc" v-if="p.description">{{ p.description?.slice(0,60) }}</span>
              </div>
            </div>
          </div>
        </div>
        <EmptyState v-else message="暂无展品" icon="📦" />
      </div>
    </div>
  </div>

  <!-- List Mode -->
  <div class="page-container" v-else>
    <div class="page-header"><h2>🏪 微展位广场</h2><p style="font-size:13px;color:var(--color-text-secondary);margin-top:4px">发现优质展商 · 免费预览展品 · 收藏感兴趣的企业</p></div>

    <div style="margin-bottom:16px;max-width:400px">
      <SearchBar v-model="keyword" placeholder="搜索微展位名称或行业..." @search="handleSearch" />
    </div>

    <div class="domain-filter">
      <button v-for="d in domains" :key="d" :class="['domain-tag', {active:activeDomain===d}]" @click="selectDomain(d)">{{ d }}</button>
    </div>
    <!-- V3.4: 展会筛选(微展位按展会归类) -->
    <div class="exh-filter" v-if="exhibitions.length">
      <button :class="['exh-tag', {active: activeExhibition === null}]" @click="selectExhibition(null)">全部展会</button>
      <button
        v-for="e in exhibitions"
        :key="e.id"
        :class="['exh-tag', {active: activeExhibition === e.id}]"
        @click="selectExhibition(e.id)"
      >🏟️ {{ (e as any).title || (e as any).name }}</button>
    </div>

    <LoadingSkeleton v-if="loading" :lines="6" />
    <div v-else-if="booths.length===0 && keyword" style="text-align:center;padding:20px;color:var(--color-text-secondary)">
      <p>🔍 没有精确匹配"{{ keyword }}"，试试换个关键词或浏览分类</p>
    </div>
    <EmptyState v-else-if="booths.length===0 && !keyword" message="暂无微展位" icon="🏪" />

    <div v-else class="mb-grid">
      <p v-if="keyword" style="grid-column:1/-1;font-size:13px;color:var(--color-text-secondary);margin-bottom:4px">搜索"{{ keyword }}"的结果 ({{ booths.length }}个)</p>
      <div v-for="b in booths" :key="b.id" class="mb-card" @click="goDetail(b.id)">
        <div class="mb-top">
          <span class="mb-tier">{{ tierBadge[b.membership_tier] || '🆓' }}</span>
          <h3>{{ b.name }}</h3>
        </div>
        <!-- V3.4: 所属展会标签 -->
        <div v-if="(b as any).exhibition_info" class="mb-exh" @click.stop="router.push('/exhibitions/' + (b as any).exhibition_info.id)">
          🏟️ {{ (b as any).exhibition_info.title }}
        </div>
        <p class="mb-desc" v-if="b.description">{{ b.description.slice(0,80) }}{{ b.description.length>80?'...':'' }}</p>
        <div class="mb-tags" v-if="b.industry_domain">
          <span class="mb-tag">{{ b.industry_domain }}</span>
        </div>
        <div class="mb-stats">
          <span>👀 {{ b.view_count || 0 }}</span>
          <span>🔍 {{ b.search_appearances || 0 }}</span>
          <span>❤️ {{ b.favorite_count || 0 }}</span>
          <span>📦 {{ b.product_count || 0 }}展品</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* List */
.domain-filter { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:20px }
.domain-tag { padding:4px 10px; border:1px solid var(--color-border); border-radius:16px; font-size:12px; background:#fff; cursor:pointer }
.domain-tag.active { background:var(--color-primary); color:#fff; border-color:var(--color-primary) }
.mb-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap:16px }
.mb-card { background:#fff; border-radius:12px; padding:20px; box-shadow:0 1px 4px rgba(0,0,0,0.04); cursor:pointer; transition:transform 0.15s }
.mb-card:hover { transform:translateY(-2px); box-shadow:0 4px 12px rgba(0,0,0,0.08) }
.mb-top { display:flex; align-items:center; gap:8px; margin-bottom:8px }
.mb-top h3 { font-size:16px; font-weight:600 }
.mb-tier { font-size:14px }
.mb-desc { font-size:13px; color:var(--color-text-secondary); margin-bottom:10px; line-height:1.5 }
.mb-tags { margin-bottom:10px }
.mb-tag { display:inline-block; padding:2px 8px; border-radius:10px; background:var(--color-primary-light); color:var(--color-primary); font-size:11px }
.mb-stats { display:flex; gap:12px; font-size:12px; color:var(--color-text-secondary); padding-top:10px; border-top:1px solid var(--color-border-lighter) }

/* Detail */
.detail-card { background:#fff; border-radius:16px; padding:32px; box-shadow:0 2px 8px rgba(0,0,0,0.04) }
.detail-header { text-align:center; margin-bottom:20px }
.detail-tier { display:inline-block; padding:4px 16px; border-radius:16px; background:linear-gradient(135deg,#f59e0b,#ef4444); color:#fff; font-size:13px; font-weight:700; margin-bottom:12px }
.detail-header h1 { font-size:24px; font-weight:700; margin-bottom:4px }
.detail-domain { font-size:14px; color:var(--color-text-secondary) }
.detail-desc { font-size:14px; color:var(--color-text-regular); line-height:1.8; margin-bottom:24px; text-align:center }
.detail-stats { display:flex; justify-content:center; gap:32px; padding:16px; background:var(--color-bg-page); border-radius:12px; margin-bottom:24px }
.dstat { text-align:center }
.dstat strong { display:block; font-size:22px; color:var(--color-primary) }
.dstat span { font-size:12px; color:var(--color-text-secondary) }
.detail-products h3 { font-size:16px; margin-bottom:12px }
.dprod-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap:12px }
.dprod-card { display:flex; gap:12px; padding:12px; background:var(--color-bg-page); border-radius:10px; cursor:pointer }
.dprod-card:hover { background:#eef2ff }
.dprod-img { width:56px; height:56px; border-radius:8px; background:#e0e7ff; display:flex; align-items:center; justify-content:center; font-size:24px; flex-shrink:0 }
.dprod-info { display:flex; flex-direction:column; gap:2px }
.dprod-info strong { font-size:14px }
.dprod-cat { font-size:11px; color:var(--color-primary) }
.dprod-desc { font-size:12px; color:var(--color-text-secondary) }
.btn-back { background:none; border:none; color:var(--color-primary); font-size:14px; cursor:pointer; padding:0 }
.btn-back:hover { text-decoration:underline }
/* V3.4: 展会筛选与所属展会 */
.exh-filter { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:16px; }
.exh-tag { padding:5px 12px; border:1px solid #c7d2fe; border-radius:16px; font-size:12px; background:#eef2ff; color:#4338ca; cursor:pointer; transition:all .2s; max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.exh-tag.active { background:#4338ca; color:#fff; border-color:#4338ca; font-weight:600; }
.mb-exh { display:inline-block; margin-bottom:8px; padding:2px 10px; border-radius:10px; background:#eef2ff; color:#4338ca; font-size:12px; cursor:pointer; }
.mb-exh:hover { background:#e0e7ff; }
.detail-exh { margin-bottom:16px; padding:14px 16px; border:1px solid #c7d2fe; border-radius:12px; background:#f5f7ff; cursor:pointer; transition:all .2s; }
.detail-exh:hover { border-color:#818cf8; box-shadow:0 2px 8px rgba(79,70,229,0.12); }
.deh-title { font-size:12px; color:#6366f1; margin-bottom:6px; }
.deh-name { font-size:15px; font-weight:700; color:#1f2937; margin-bottom:6px; }
.deh-meta { display:flex; gap:14px; flex-wrap:wrap; font-size:13px; color:#4b5563; margin-bottom:8px; }
.deh-link { font-size:13px; color:#4338ca; font-weight:500; }
</style>
