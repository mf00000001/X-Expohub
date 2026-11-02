<script setup lang="ts">
// 平台运营（管理员）：总览 + 档位计费 + 订阅分配 + 批量导入展会
import { onMounted, ref } from 'vue'
import { platformApi, type PlanItem } from '@/api/platform'

const overview = ref<Record<string, number> | null>(null)
const plans = ref<PlanItem[]>([])
const message = ref('')

const planForm = ref({ tier: 'standard', name: '标准版', monthly_fee_yuan: '99', features: '' })
const assignPlanId = ref<number>(0)
const importText = ref('')
const importResult = ref('')

// 平台总览字段：后端英文 key → 中文展示；未收录的 key 原样显示，避免丢信息
const OVERVIEW_LABELS: Record<string, string> = {
  users_count: '用户总数',
  exhibitions_count: '展会总数',
  orders_count: '订单总数',
  paid_orders_count: '已支付订单',
  tickets_count: '票券总数',
  checkin_logs_count: '核销记录',
  audit_logs_count: '审计日志',
  plans_count: '档位数量',
}

// 计费档位：技术标识（tier）保留英文，另给中文称谓
const TIER_LABELS: Record<string, string> = {
  basic: '基础版',
  standard: '标准版',
  pro: '专业版',
}

// 档位下拉选项：中文称谓 + 英文技术标识，便于对照后端
const TIER_OPTIONS = [
  { value: 'basic', label: '基础版（basic）' },
  { value: 'standard', label: '标准版（standard）' },
  { value: 'pro', label: '专业版（pro）' },
]

function overviewLabel(key: string): string {
  return OVERVIEW_LABELS[key] || key
}

function tierLabel(tier: string): string {
  return TIER_LABELS[tier] || tier
}

async function loadAll() {
  try {
    const [ov, pl] = await Promise.all([platformApi.overview(), platformApi.plans()])
    overview.value = ov
    plans.value = pl.list || []
    if (plans.value.length && !assignPlanId.value) assignPlanId.value = plans.value[0].id
  } catch (e: any) {
    message.value = e?.response?.data?.message || '加载失败'
  }
}

async function upsert() {
  message.value = ''
  try {
    await platformApi.upsertPlan({
      tier: planForm.value.tier,
      name: planForm.value.name,
      monthly_fee_cents: Math.round(parseFloat(planForm.value.monthly_fee_yuan || '0') * 100),
      // 兼容中英文逗号 / 顿号分隔
      features: planForm.value.features.split(/[,，、]/).map((s) => s.trim()).filter(Boolean)
    })
    message.value = '档位已保存'
    await loadAll()
  } catch (e: any) {
    message.value = e?.response?.data?.message || '保存失败'
  }
}

async function assign() {
  message.value = ''
  if (!plans.value.length || !plans.value.some((p) => p.id === assignPlanId.value)) {
    message.value = '请先在上方创建档位'
    return
  }
  try {
    await platformApi.assignPlan('default', assignPlanId.value)
    message.value = '订阅已更新（租户 default）'
  } catch (e: any) {
    message.value = e?.response?.data?.message || '分配失败'
  }
}

async function doImport() {
  message.value = ''
  // 每行 TSV：标题<TAB>开始<TAB>结束<TAB>地点<TAB>状态(可选)
  const rows = importText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split('\t')
      return {
        title: parts[0],
        start_date: parts[1],
        end_date: parts[2],
        location: parts[3],
        ...(parts[4] ? { status: parts[4] } : {})
      }
    })
  if (!rows.length) {
    message.value = '请先粘贴至少一行数据'
    return
  }
  try {
    const r = await platformApi.importExhibitions(rows)
    importResult.value = `导入完成：成功 ${r.success_count}/${r.total}`
    if (r.results.length) {
      const fails = r.results.filter((x) => !x.ok)
      if (fails.length) importResult.value += `；失败 ${fails.length} 行（如「${fails[0]?.reason}」）`
    }
    await loadAll()
  } catch (e: any) {
    message.value = e?.response?.data?.message || '导入失败'
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="container main-content">
    <h2 class="mb-md">🛠️ 平台运营（管理员）</h2>
    <p v-if="message" class="form-error">{{ message }}</p>

    <div class="card p-md mb-md">
      <h3 class="mb-sm">平台总览</h3>
      <div v-if="overview" class="flex gap-md flex-wrap">
        <div v-for="(v, k) in overview" :key="k" class="tag tag-info">{{ overviewLabel(k) }}：{{ v }}</div>
      </div>
    </div>

    <div class="card p-md mb-md">
      <h3 class="mb-sm">档位计费</h3>
      <div class="flex gap-md flex-wrap">
        <div class="flex-1"><label class="form-label">档位（tier）</label>
          <select v-model="planForm.tier" class="form-select">
            <option v-for="t in TIER_OPTIONS" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select></div>
        <div class="flex-1"><label class="form-label">名称</label>
          <input v-model="planForm.name" class="form-input" /></div>
        <div class="flex-1"><label class="form-label">月费（元）</label>
          <input v-model="planForm.monthly_fee_yuan" class="form-input" type="number" min="0" /></div>
        <div class="flex-1"><label class="form-label">功能（逗号分隔）</label>
          <input v-model="planForm.features" class="form-input" placeholder="例如：售票、现场核销、AI 助手" /></div>
      </div>
      <button class="btn btn-primary mt-md" @click="upsert">保存档位</button>

      <h4 class="mt-lg mb-sm">已建档档位</h4>
      <div v-for="p in plans" :key="p.id" class="flex justify-between items-center mb-sm">
        <span><strong>{{ p.name }}</strong> <span class="tag tag-warning">¥{{ (p.monthly_fee_cents / 100).toFixed(2) }}/月</span>
          <span class="tag tag-info">{{ p.features.join(', ') || '无' }}</span></span>
        <span class="tag">#{{ p.id }} {{ tierLabel(p.tier) }}</span>
      </div>
    </div>

    <div class="card p-md mb-md">
      <h3 class="mb-sm">租户订阅（当前租户标识：default）</h3>
      <select v-model.number="assignPlanId" class="form-select" style="max-width: 240px">
        <option v-for="p in plans" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <button class="btn btn-outline ml-sm" :disabled="!plans.length" @click="assign">分配订阅</button>
    </div>

    <div class="card p-md">
      <h3 class="mb-sm">批量导入展会（TSV：标题 / 开始 / 结束 / 地点 / 状态选填）</h3>
      <textarea v-model="importText" class="form-textarea" rows="4"
        placeholder="2026 智能出行展&#9;2026-11-01T09:00:00&#9;2026-11-03T18:00:00&#9;北京亦创国际会展中心&#9;draft" />
      <button class="btn btn-primary mt-md" @click="doImport">导入</button>
      <p v-if="importResult" class="tag tag-success mt-md">{{ importResult }}</p>
    </div>
  </div>
</template>
