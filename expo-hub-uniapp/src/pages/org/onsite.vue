<template>
  <view class="page">
    <text class="h">现场核销台（主办方/管理员）</text>

    <picker :range="exhOptions" range-key="title" @change="onPickExh">
      <view class="picker">{{ curExhTitle || '选择展会' }} ▾</view>
    </picker>

    <view class="panel">
      <text class="lbl">二维码载荷（{"t":"票号","s":"签名"}）或手动输入：</text>
      <textarea class="ta" v-model="qrRaw" placeholder='{"t":"...","s":"..."}' />
      <button class="btn sm" size="mini" @click="applyQr">解析载荷</button>
      <view class="row2">
        <input class="ipt" v-model="ticketNo" placeholder="票号" />
        <input class="ipt" v-model="signature" placeholder="签名" />
      </view>
      <view class="btns">
        <button class="btn ok" size="mini" @click="doCheckin">✅ 核销</button>
        <button class="btn rev" size="mini" @click="doRevoke">↩️ 撤销</button>
        <button class="btn" size="mini" @click="doVerify">🔍 验票</button>
      </view>
    </view>
    <text class="msg" v-if="message">{{ message }}</text>

    <view class="panel" v-if="stats">
      <text class="lbl">统计</text>
      <text class="stat">入场 {{ stats.checked_in_count ?? 0 }} / 总数 {{ stats.total_tickets ?? 0 }}</text>
      <text class="stat">票种分布：{{ distText }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { onsiteApi } from '@/api/onsite'
import { ticketingApi } from '@/api/ticketing'
import { request, getToken } from '@/utils/request'

const exhibitions = ref<any[]>([])
const exhIndex = ref(-1)
const exhibitionId = ref(0)
const curExhTitle = computed(() => (exhIndex.value >= 0 ? exhibitions.value[exhIndex.value]?.title : ''))
const exhOptions = computed(() => exhibitions.value)
const qrRaw = ref('')
const ticketNo = ref('')
const signature = ref('')
const message = ref('')
const stats = ref<any>(null)
const distText = ref('')

onLoad(() => {
  if (!getToken()) return uni.reLaunch({ url: '/pages/login/login' })
  loadExhs()
})
onShow(() => {
  if (exhibitionId.value) loadStats()
})

function onPickExh(e: any) {
  exhIndex.value = Number(e.detail.value)
  exhibitionId.value = exhibitions.value[exhIndex.value]?.id || 0
  loadStats()
}

async function loadExhs() {
  try {
    const u: any = uni.getStorageSync('expo_user')
    const me = u ? JSON.parse(u) : null
    const res: any = await request({ url: '/exhibitions?page_size=100' })
    let rows = res?.list || []
    if (me && me.role !== 'admin') rows = rows.filter((x: any) => x.organizer_id === me.id)
    exhibitions.value = rows || []
  } catch (e) {
    uni.showToast({ title: '加载展会失败', icon: 'none' })
  }
}

function applyQr() {
  try {
    const p = JSON.parse(qrRaw.value)
    ticketNo.value = p.t || ''
    signature.value = p.s || ''
    message.value = ticketNo.value ? '已解析载荷' : '载荷缺 t 字段'
  } catch {
    message.value = '载荷不是合法 JSON'
  }
}

async function guard(): Promise<boolean> {
  if (!exhibitionId.value) {
    message.value = '请先选择展会'
    return false
  }
  return true
}

async function doCheckin() {
  if (!(await guard())) return
  if (!ticketNo.value || !signature.value) {
    message.value = '请填票号与签名'
    return
  }
  try {
    const r = await onsiteApi.checkin({ exhibition_id: exhibitionId.value, ticket_no: ticketNo.value, signature: signature.value })
    message.value = r.ok ? '✅ ' + r.reason : '❌ ' + r.reason
    loadStats()
    reset()
  } catch (e: any) {
    message.value = e.message || '核销失败'
  }
}

async function doVerify() {
  if (!(await guard())) return
  if (!ticketNo.value || !signature.value) {
    message.value = '请填票号与签名'
    return
  }
  try {
    const r = await ticketingApi.verifyTicket(ticketNo.value, signature.value)
    message.value = r.valid ? `✅ 票券有效（${r.status}）` : `❌ 不可用（${r.status}）`
  } catch (e: any) {
    message.value = e.message || '验票失败'
  }
}

async function doRevoke() {
  if (!(await guard())) return
  if (!ticketNo.value) {
    message.value = '请填票号'
    return
  }
  try {
    await onsiteApi.revoke(ticketNo.value, exhibitionId.value)
    message.value = '✅ 已撤销核销'
    loadStats()
    reset()
  } catch (e: any) {
    message.value = e.message || '撤销失败'
  }
}

function reset() {
  ticketNo.value = ''
  signature.value = ''
  qrRaw.value = ''
}

async function loadStats() {
  try {
    const s: any = await onsiteApi.stats(exhibitionId.value)
    stats.value = s
    const by = s?.by_ticket_type || s?.distribution || {}
    distText.value = Object.keys(by).map((k) => `${k}:${by[k]}`).join('，') || '—'
  } catch {
    stats.value = null
  }
}
</script>

<style scoped>
.page { padding: 16px; background: #f5f6f8; min-height: 100vh; }
.h { font-size: 18px; font-weight: 700; display: block; margin-bottom: 12px; }
.picker { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 12px; font-size: 15px; }
.panel { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 12px; }
.lbl { display: block; font-size: 13px; color: #333; margin-bottom: 8px; }
.ta { width: 100%; height: 64px; border: 1px solid #e0e2e8; border-radius: 8px; padding: 8px; font-size: 12px; box-sizing: border-box; margin-bottom: 8px; }
.ipt { border: 1px solid #e0e2e8; border-radius: 8px; padding: 8px 10px; font-size: 13px; margin-bottom: 8px; width: 48%; box-sizing: border-box; }
.row2 { display: flex; justify-content: space-between; }
.btns { display: flex; gap: 8px; margin-top: 6px; }
.btn { background: #4f6ef7; color: #fff; border-radius: 6px; }
.btn.ok { background: #2f9e5f; }
.btn.rev { background: #e6a23c; }
.msg { display: block; font-size: 13px; color: #333; margin-bottom: 10px; }
.stat { display: block; font-size: 13px; color: #666; margin-top: 6px; }
</style>
