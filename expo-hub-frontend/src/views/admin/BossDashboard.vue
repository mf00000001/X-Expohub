<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api/index'

const data = ref<any>(null)
const loading = ref(true)

onMounted(async () => {
  try { const r: any = await http.get('/admin/boss'); data.value = r?.data || r } catch {}
  finally { loading.value = false }
})
</script>

<template>
  <div class="boss-page">
    <h1>📊 Boss看板</h1>
    <p style="color:var(--color-text-secondary);margin-bottom:24px">平台核心指标一览</p>

    <div v-if="loading" style="text-align:center;padding:60px">加载中...</div>

    <template v-else-if="data">
      <!-- KPI行 -->
      <div class="kpi-row">
        <div class="kpi-card blue"><strong>{{ data.users?.total }}</strong><span>总用户</span></div>
        <div class="kpi-card green"><strong>{{ data.content?.products }}</strong><span>展品</span></div>
        <div class="kpi-card purple"><strong>{{ data.matches?.total }}</strong><span>匹配</span></div>
        <div class="kpi-card orange"><strong>{{ data.matches?.rate }}%</strong><span>匹配成功率</span></div>
      </div>

      <!-- 用户分布 -->
      <div class="card section">
        <h3>👥 用户分布</h3>
        <div class="bar-row">
          <div class="bar-item"><span class="bar-label">展商</span><div class="bar"><div class="bar-fill blue" :style="{width:(data.users?.exhibitors/data.users?.total*100)+'%'}"></div></div><span>{{ data.users?.exhibitors }}</span></div>
          <div class="bar-item"><span class="bar-label">买家</span><div class="bar"><div class="bar-fill green" :style="{width:(data.users?.buyers/data.users?.total*100)+'%'}"></div></div><span>{{ data.users?.buyers }}</span></div>
          <div class="bar-item"><span class="bar-label">游客</span><div class="bar"><div class="bar-fill gray" :style="{width:(data.users?.visitors/data.users?.total*100)+'%'}"></div></div><span>{{ data.users?.visitors }}</span></div>
        </div>
      </div>

      <!-- 转化漏斗 -->
      <div class="card section">
        <h3>🔽 转化漏斗</h3>
        <div class="funnel">
          <div class="f-step"><span class="f-num">{{ (data.funnel?.page_views||0).toLocaleString() }}</span><span class="f-label">页面浏览</span></div>
          <div class="f-arrow">↓</div>
          <div class="f-step"><span class="f-num">{{ data.funnel?.registrations || 0 }}</span><span class="f-label">展会报名</span></div>
          <div class="f-arrow">↓</div>
          <div class="f-step"><span class="f-num">{{ data.funnel?.micro_booths_created || 0 }}</span><span class="f-label">微展位创建</span></div>
          <div class="f-arrow">↓</div>
          <div class="f-step highlight"><span class="f-num">{{ data.funnel?.successful_matches || 0 }}</span><span class="f-label">成功匹配</span></div>
        </div>
      </div>

      <!-- 内容与互动 -->
      <div class="two-col">
        <div class="card section">
          <h3>📦 内容</h3>
          <div class="stat-list">
            <div class="sl-item"><span>展会</span><strong>{{ data.content?.exhibitions }}</strong></div>
            <div class="sl-item"><span>展位</span><strong>{{ data.content?.booths }}</strong></div>
            <div class="sl-item"><span>采购需求</span><strong>{{ data.content?.procurements }}</strong></div>
            <div class="sl-item"><span>微展位</span><strong>{{ data.micro_booths?.total }} ({{ data.micro_booths?.views }}浏览)</strong></div>
          </div>
        </div>
        <div class="card section">
          <h3>📈 互动</h3>
          <div class="stat-list">
            <div class="sl-item"><span>积分发放</span><strong>{{ data.engagement?.points_distributed }}</strong></div>
            <div class="sl-item"><span>通知推送</span><strong>{{ data.engagement?.notifications_sent }}</strong></div>
            <div class="sl-item"><span>报名数</span><strong>{{ data.engagement?.registrations }}</strong></div>
            <div class="sl-item"><span>匹配成功</span><strong>{{ data.matches?.accepted }}</strong></div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.boss-page { max-width:1000px; margin:0 auto; padding:24px }
.kpi-row { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:24px }
.kpi-card { padding:20px; border-radius:12px; text-align:center; color:#fff }
.kpi-card strong { display:block; font-size:32px; font-weight:800 }
.kpi-card span { font-size:13px; opacity:0.8 }
.blue { background:linear-gradient(135deg,#3b82f6,#6366f1) }
.green { background:linear-gradient(135deg,#10b981,#34d399) }
.purple { background:linear-gradient(135deg,#8b5cf6,#a78bfa) }
.orange { background:linear-gradient(135deg,#f59e0b,#fbbf24) }
.section { margin-bottom:20px; padding:20px }
.section h3 { margin-bottom:16px; font-size:16px }
.bar-row { display:flex; flex-direction:column; gap:10px }
.bar-item { display:flex; align-items:center; gap:10px; font-size:13px }
.bar-label { width:40px; text-align:right; color:var(--color-text-secondary) }
.bar { flex:1; height:20px; background:var(--color-bg-page); border-radius:10px; overflow:hidden }
.bar-fill { height:100%; border-radius:10px }
.bar-fill.blue { background:#3b82f6 } .bar-fill.green { background:#10b981 } .bar-fill.gray { background:#9ca3af }
.funnel { display:flex; align-items:center; gap:12px; flex-wrap:wrap; justify-content:center }
.f-step { text-align:center; padding:16px; background:var(--color-bg-page); border-radius:10px; min-width:100px }
.f-step.highlight { background:linear-gradient(135deg,#fef3c7,#fde68a); border:2px solid #f59e0b }
.f-num { display:block; font-size:24px; font-weight:800 }
.f-label { font-size:12px; color:var(--color-text-secondary) }
.f-arrow { font-size:20px; color:var(--color-text-secondary) }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:20px }
.stat-list { display:flex; flex-direction:column; gap:8px }
.sl-item { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--color-border-lighter); font-size:14px }
.sl-item strong { color:var(--color-primary) }
@media(max-width:768px){ .kpi-row{grid-template-columns:repeat(2,1fr)} .two-col{grid-template-columns:1fr} }
</style>
