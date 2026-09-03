<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { microBoothApi, type MicroBooth } from '@/api/micro-booth'
import { productApi } from '@/api/product'
import http from '@/api/index'
import { validateInput } from '@/utils/validate'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const booths = ref<MicroBooth[]>([])
const loading = ref(true)
const showCreate = ref(false)
const createForm = ref({ name: '', description: '', industry_domain: '' })
const saving = ref(false)
const selectedBooth = ref<MicroBooth | null>(null)
const myProducts = ref<any[]>([])
const showAddProduct = ref(false)

onMounted(async () => { await loadData() })

async function loadData() {
  loading.value = true
  try {
    const [mb, mp] = await Promise.all([
      microBoothApi.getMy(),
      productApi.getMyProducts({ page_size: 100 }).catch(() => ({ list: [] })),
    ])
    booths.value = mb || []
    myProducts.value = (mp as any)?.list || (mp as any)?.items || []
  } catch(e) { console.error('加载微展位失败', e); booths.value = [] } finally { loading.value = false }
}

async function handleCreate() {
  if (!createForm.value.name) return
  const v3 = validateInput(createForm.value.description || ''); if (!v3.valid) { alert(v3.reason); return }
  saving.value = true
  try {
    await microBoothApi.create(createForm.value)
    showCreate.value = false
    createForm.value = { name: '', description: '', industry_domain: '' }
    alert('🎉 微展位创建成功！\n\n已上线微展位广场，预计每天100+买家浏览。\n同类微展位平均：浏览200+ / 收藏15+ / 预约3+')
    await loadData()
  } finally { saving.value = false }
}

function openBoothDetail(b: MicroBooth) {
  router.push('/micro-booths/' + b.id)
}

async function handleUpgrade(id: number, tier: string) {
  alert('功能开发中，敬请期待')
}

async function handleAddProduct(boothId: number, productId: number) {
  try {
    await microBoothApi.addProduct(boothId, productId)
    selectedBooth.value = null
    await loadData()
  } catch (e: any) { alert(e?.response?.data?.message || '添加失败') }
}

async function handleRemoveProduct(boothId: number, productId: number) {
  if (!confirm('确定移除此展品？')) return
  await microBoothApi.removeProduct(boothId, productId)
  await loadData()
}

async function handleDelete(id: number, name: string) {
  if (!confirm(`确定删除微展位"${name}"？此操作不可恢复。`)) return
  try { await http.delete(`/micro-booths/${id}`); alert('已删除'); await loadData() }
  catch(e: any) { alert(e?.response?.data?.message || '删除失败') }
}

const tierLabel: Record<string, string> = { free: '🆓 免费版', regular: '⭐ VIP会员', flagship: '👑 旗舰会员' }
const tierColor: Record<string, string> = { free: '#6b7280', regular: '#3b82f6', flagship: '#f59e0b' }
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h2>🏪 我的微展位</h2>
      <button class="btn btn-primary" @click="showCreate = !showCreate">
        {{ showCreate ? '取消' : '+ 创建微展位' }}
      </button>
    </div>

    <!-- 创建表单 -->
    <div class="card" v-if="showCreate" style="margin-bottom:24px">
      <h3 style="margin-bottom:16px">新建微展位</h3>
      <div class="form-group"><label>微展位名称 *</label><input v-model="createForm.name" class="form-input" placeholder="例如：XX科技产品展示" /></div>
      <div class="form-group"><label>简介</label><textarea v-model="createForm.description" class="form-textarea" rows="3" placeholder="简单介绍你的展品和公司" /></div>
      <div class="form-group"><label>行业领域</label><select v-model="createForm.industry_domain" class="form-input"><option value="">请选择行业</option><option v-for="d in ['电子及家电','照明','车辆及配件','五金工具','机械','建材','化工产品','能源','日用消费品','礼品','纺织服装','鞋类','家居装饰品','办公箱包及休闲用品','食品','医药及医疗保健','AI/科技','综合服务']" :key="d" :value="d">{{ d }}</option></select></div>
      <button class="btn btn-primary" :disabled="saving" @click="handleCreate">{{ saving ? '创建中...' : '创建免费微展位' }}</button>
      <p style="font-size:12px;color:var(--color-text-secondary);margin-top:8px">🎁 免费版可挂1-3个展品，升级会员解锁更多</p>
    </div>

    <LoadingSkeleton v-if="loading" :lines="3" />
    <EmptyState v-else-if="booths.length === 0" message="还没有微展位" icon="🏪">
      <button class="btn btn-primary" @click="showCreate = true">创建第一个微展位</button>
    </EmptyState>

    <div v-else class="card-grid">
      <div v-for="b in booths" :key="b.id" class="card booth-card">
        <div class="booth-header">
          <h3 @click="openBoothDetail(b)" style="cursor:pointer">{{ b.name }}</h3>
          <span class="tag" :style="{background: tierColor[b.membership_tier]+'20', color: tierColor[b.membership_tier]}">
            {{ tierLabel[b.membership_tier] }}
          </span>
        </div>
        <p class="booth-desc" v-if="b.description">{{ b.description }}</p>

        <!-- 使用情况 -->
        <div class="usage-bar">
          <div class="usage-info">
            <span>展品 {{ b.product_count }}/{{ b.product_limit || '∞' }}</span>
            <span v-if="b.product_limit > 0 && b.product_count >= b.product_limit" style="color:var(--color-warning);font-size:12px">⚠️ 已满，升级解锁更多</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: b.product_limit ? (b.product_count/b.product_limit*100)+'%' : '100%', background: b.product_count >= b.product_limit ? '#f59e0b' : '#10b981' }"></div>
          </div>
        </div>

        <!-- 数据卡片 -->
        <div class="mini-stats">
          <div class="mini-stat"><strong>{{ b.view_count }}</strong><span>浏览</span></div>
          <div class="mini-stat"><strong>{{ b.search_appearances }}</strong><span>搜索曝光</span></div>
          <div class="mini-stat"><strong>{{ b.favorite_count }}</strong><span>收藏</span></div>
        </div>

        <!-- 升级提示 -->
        <div class="upgrade-nudge" v-if="(b.view_count||0) + (b.favorite_count||0) > 5 && b.membership_tier === 'free'">
          🎯 已有{{ b.view_count }}人浏览、{{ b.favorite_count }}人收藏！升级会员解锁首页推荐位，浏览量预计翻3倍
        </div>

        <!-- 操作按钮 -->
        <div class="booth-actions">
          <button class="btn btn-sm btn-primary-outline" @click="selectedBooth = b; showAddProduct = true">+ 添加展品</button>
          <template v-if="b.membership_tier === 'free'">
            <button class="btn btn-sm btn-default" @click="handleUpgrade(b.id, 'regular')">升级VIP会员</button>
            <button class="btn btn-sm btn-warning" @click="handleUpgrade(b.id, 'flagship')">升级旗舰</button>
          </template>
          <template v-if="b.membership_tier === 'regular'">
            <button class="btn btn-sm btn-warning" @click="handleUpgrade(b.id, 'flagship')">升级旗舰</button>
          </template>
          <button class="btn btn-sm btn-danger" @click="handleDelete(b.id, b.name)">删除</button>
        </div>

        <!-- 添加展品弹窗 -->
        <div v-if="showAddProduct && selectedBooth?.id === b.id" class="add-prod-overlay" @click.self="showAddProduct=false">
          <div class="add-prod-card">
            <h4>选择展品添加到"{{ b.name }}"</h4>
            <div v-if="myProducts.length===0" style="padding:20px;color:var(--color-text-secondary)">暂无展品，请先去"添加展品"创建</div>
            <div v-else class="prod-select-list">
              <div v-for="p in myProducts" :key="p.id" class="prod-opt" @click="handleAddProduct(b.id, p.id)">
                <span>{{ p.name }}</span><span class="text-muted">{{ p.category }}</span>
              </div>
            </div>
            <button class="btn btn-sm btn-default" @click="showAddProduct=false" style="margin-top:12px">取消</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.booth-card { display: flex; flex-direction: column; gap: 12px; }
.booth-header { display: flex; justify-content: space-between; align-items: center; }
.booth-header h3 { font-size: 17px; }
.booth-desc { font-size: 13px; color: var(--color-text-secondary); }
.usage-bar { margin: 4px 0; }
.usage-info { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px; }
.progress-bar { height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.mini-stats { display: flex; gap: 16px; padding: 8px 0; border-top: 1px solid var(--color-border-lighter); border-bottom: 1px solid var(--color-border-lighter); }
.mini-stat { text-align: center; flex: 1; }
.mini-stat strong { display: block; font-size: 18px; color: var(--color-primary); }
.mini-stat span { font-size: 11px; color: var(--color-text-secondary); }
.booth-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.btn-warning { background: #fef3c7; color: #d97706; border: 1px solid #fcd34d; cursor: pointer; padding: 4px 10px; border-radius: 4px; font-size: 12px; }
.upgrade-nudge { padding:10px 14px; background:linear-gradient(135deg,#fef3c7,#fef9c3); border-radius:8px; font-size:12px; color:#92400e; line-height:1.5 }
.add-prod-overlay { position:fixed;inset:0;background:rgba(0,0,0,0.4);display:flex;justify-content:center;align-items:center;z-index:200 }
.add-prod-card { background:#fff;border-radius:12px;padding:24px;width:400px;max-width:90vw;max-height:70vh;overflow-y:auto }
.add-prod-card h4 { margin-bottom:12px }
.prod-select-list { display:flex;flex-direction:column;gap:6px;max-height:300px;overflow-y:auto }
.prod-opt { padding:10px 12px;background:var(--color-bg-page);border-radius:8px;cursor:pointer;display:flex;justify-content:space-between }
.prod-opt:hover { background:var(--color-primary-light) }
.btn-danger { background:var(--color-danger-light);color:var(--color-danger);border:1px solid var(--color-danger-lighter) }
</style>
