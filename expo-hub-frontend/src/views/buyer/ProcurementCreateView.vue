<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/index'
import { validateInput } from '@/utils/validate'

const router = useRouter()
const title = ref('')
const category = ref('')
const quantity = ref<number | null>(null)
const unit = ref('件')
const description = ref('')
const budget = ref<number | null>(null)
const deadline = ref('')
const saving = ref(false)
const errorMsg = ref('')

const categories = [
  '电子及家电','照明','车辆及配件','五金工具','机械','建材','化工产品','能源',
  '日用消费品','礼品','纺织服装','鞋类','家居装饰品','办公箱包及休闲用品','食品',
  '医药及医疗保健','AI/科技','综合服务'
]

async function handleCreate() {
  if (!title.value || !category.value) { errorMsg.value = '请填写标题和品类'; return }
  const v = validateInput(title.value + (description.value || '')); if (!v.valid) { errorMsg.value = v.reason; return }
  saving.value = true; errorMsg.value = ''
  try {
    await http.post('/procurements', {
      title: title.value, category: category.value,
      quantity: quantity.value, unit: unit.value,
      description: description.value, budget_max: budget.value, deadline: deadline.value || undefined
    })
    alert('采购需求发布成功！')
    router.push('/procurements')
  } catch (e: any) { errorMsg.value = e?.response?.data?.message || '发布失败' }
  finally { saving.value = false }
}
</script>

<template>
  <div class="page-container" style="max-width:600px;margin:0 auto">
    <h2 style="margin-bottom:20px">📦 发布采购需求</h2>
    <div class="card" style="padding:24px">
      <div class="form-group"><label>采购标题 *</label><input v-model="title" class="form-input" placeholder="例如：采购智能家电控制板1000套" /></div>
      <div class="form-group"><label>品类 *</label><select v-model="category" class="form-input"><option value="">请选择</option><option v-for="c in categories" :key="c" :value="c">{{ c }}</option></select></div>
      <div class="form-row">
        <div class="form-group"><label>数量</label><input v-model.number="quantity" class="form-input" type="number" placeholder="1000" /></div>
        <div class="form-group"><label>单位</label><select v-model="unit" class="form-input"><option>件</option><option>套</option><option>台</option><option>kg</option><option>箱</option></select></div>
      </div>
      <div class="form-group"><label>截止日期</label><input v-model="deadline" class="form-input" type="date" /></div>
      <div class="form-group"><label>详细描述</label><textarea v-model="description" class="form-textarea" rows="4" placeholder="描述产品规格、认证要求、交货期等" /></div>
      <p v-if="errorMsg" style="color:var(--color-danger);font-size:13px;margin-bottom:12px">{{ errorMsg }}</p>
      <button class="btn btn-primary btn-lg" style="width:100%" :disabled="saving" @click="handleCreate">{{ saving ? '发布中...' : '发布采购需求' }}</button>
    </div>
  </div>
</template>

<style scoped>
.form-row { display:grid; grid-template-columns:1fr 1fr; gap:12px }
</style>
