<script setup lang="ts">
// 现场核销台（主办方/管理员）：单张核销/撤销 + 批量 + 实时统计
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { onsiteApi, type OnsiteStats } from '@/api/onsite'
import { ticketingApi } from '@/api/ticketing'
import { exhibitionApi } from '@/api/exhibition'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()
const exhibitionId = ref<number>(Number(route.query.exhibitionId) || 0)
// 可选展会：admin 看全部；主办方只看自己的
const myExhs = ref<{ id: number; title: string }[]>([])

async function loadExhibitions() {
  const res = await exhibitionApi.getList({ page_size: 100 }).catch(() => ({ list: [] }))
  let rows = (res as any).list || []
  const me = userStore.profile?.id
  if (userStore.userRole !== 'admin' && me) {
    rows = rows.filter((e: any) => e.organizer_id === me)
  }
  myExhs.value = rows.map((e: any) => ({ id: e.id, title: e.title || e.name || `展会#${e.id}` }))
  const q = Number(route.query.exhibitionId) || 0
  if (myExhs.value.some((x) => x.id === q)) exhibitionId.value = q
  else exhibitionId.value = myExhs.value[0]?.id || q || 0
  await loadStats()
}

const message = ref('')
const lastResult = ref('')
const stats = ref<OnsiteStats | null>(null)

// 单张核销：直接粘贴 qr_payload JSON（含 t/s）或手动输入票号+签名
const ticketNo = ref('')
const signature = ref('')
const qrRaw = ref('')

async function applyQr() {
  try {
    const payload = JSON.parse(qrRaw.value)
    ticketNo.value = payload.t || ''
    signature.value = payload.s || ''
    message.value = ticketNo.value ? '已解析二维码载荷' : '载荷缺少票号字段 t'
  } catch {
    message.value = '二维码载荷不是合法 JSON（应为 {"t":票号,"s":签名}）'
  }
}

async function checkin() {
  message.value = ''
  if (!ticketNo.value || !signature.value) {
    message.value = '请先填写票号与签名（或粘贴二维码载荷）'
    return
  }
  try {
    const r = await onsiteApi.checkin({ exhibition_id: exhibitionId.value, ticket_no: ticketNo.value, signature: signature.value })
    message.value = r.ok ? `✅ ${r.reason}` : `❌ ${r.reason}`
    lastResult.value = message.value
    await loadStats()
    reset()
  } catch (e: any) {
    message.value = e?.response?.data?.message || '核销失败'
  }
}

async function revoke() {
  message.value = ''
  if (!ticketNo.value) {
    message.value = '请填写要撤销的票号'
    return
  }
  try {
    await onsiteApi.revoke(ticketNo.value, exhibitionId.value)
    message.value = '✅ 已撤销核销，票券恢复有效'
    await loadStats()
    reset()
  } catch (e: any) {
    message.value = e?.response?.data?.message || '撤销失败'
  }
}

async function verifySig() {
  message.value = ''
  if (!ticketNo.value || !signature.value) return checkin()
  try {
    const r = await ticketingApi.verify(ticketNo.value, signature.value)
    message.value = r.valid ? `✅ 票券有效（状态 ${r.status}）` : `❌ 票券不可用（状态 ${r.status}）`
  } catch (e: any) {
    message.value = e?.response?.data?.message || '校验失败'
  }
}

async function loadStats() {
  if (!exhibitionId.value) return
  try {
    stats.value = await onsiteApi.stats(exhibitionId.value)
  } catch {
    stats.value = null
  }
}

function reset() {
  ticketNo.value = ''
  signature.value = ''
  qrRaw.value = ''
}

onMounted(loadExhibitions)
</script>

<template>
  <div class="container main-content">
    <div class="flex justify-between items-center mb-md">
      <h2>🎯 现场核销台</h2>
      <a class="btn btn-outline btn-sm" href="/tickets/my" @click.prevent>← 返回</a>
    </div>

    <div class="flex items-center gap-sm mb-md">
      <label class="form-label mb-0">选择展会：</label>
      <select v-model.number="exhibitionId" class="form-input" style="max-width: 360px" @change="loadStats">
        <option :value="0" disabled>— 请选择展会 —</option>
        <option v-for="e in myExhs" :key="e.id" :value="e.id">{{ e.title }}</option>
      </select>
      <button v-if="!myExhs.length" class="btn btn-outline btn-sm" @click="loadExhibitions">刷新展会</button>
      <button class="btn btn-outline btn-sm" @click="loadStats">加载统计</button>
    </div>

    <div class="card p-md mb-md">
      <h3 class="mb-sm">扫码/输入核销</h3>
      <label class="form-label">粘贴二维码载荷（可选，自动解析票号与签名）</label>
      <input v-model="qrRaw" class="form-input" placeholder='{"t":"T123...","s":"签名"}' @change="applyQr" />
      <div class="flex gap-md mt-sm">
        <div class="flex-1">
          <label class="form-label">票号</label>
          <input v-model="ticketNo" class="form-input" placeholder="Txxxxxxxxxxxxxx" />
        </div>
        <div class="flex-1">
          <label class="form-label">签名</label>
          <input v-model="signature" class="form-input" placeholder="16 位 HMAC 签名" />
        </div>
      </div>
      <div class="flex gap-sm mt-md">
        <button class="btn btn-success" @click="checkin">核销入场</button>
        <button class="btn btn-outline" @click="verifySig">仅验票</button>
        <button class="btn btn-danger" @click="revoke">撤销核销</button>
      </div>
      <p v-if="message" :class="message.includes('✅') ? 'tag tag-success mt-md' : 'form-error mt-md'">{{ message }}</p>
    </div>

    <div class="card p-md">
      <h3 class="mb-sm">到场统计</h3>
      <p v-if="!stats">暂无统计（先设置展会 ID 并加载）</p>
      <template v-else>
        <div class="flex gap-lg mb-md">
          <div class="tag tag-success">入场 {{ stats.checkin_count }}</div>
          <div class="tag tag-danger">撤销 {{ stats.revoke_count }}</div>
        </div>
        <h4 class="mb-sm">票种分布</h4>
        <div v-for="(cnt, name) in stats.by_ticket_type" :key="name" class="flex justify-between mb-sm">
          <span>{{ name }}</span><span>{{ cnt }}</span>
        </div>
        <h4 class="mb-sm">最新流水</h4>
        <div v-for="l in stats.latest" :key="l.ticket_no + l.action" class="tag tag-info mb-sm mr-sm">
          {{ l.action === 'checkin' ? '入场' : '撤销' }} {{ l.ticket_no }} · {{ l.ticket_type_name }}
        </div>
      </template>
    </div>
  </div>
</template>
