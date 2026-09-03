<template>
  <view class="page">
    <view class="head">
      <text class="h">{{ title || '购买门票' }}</text>
      <text class="sub">选择票种下单（免费票直接出票，付费票走演示支付）</text>
    </view>

    <view class="card" v-for="t in types" :key="t.id">
      <view class="row">
        <text class="name">{{ t.name }}</text>
        <text class="price">{{ t.price_cents === 0 ? '免费' : '¥' + (t.price_cents / 100).toFixed(2) }}</text>
      </view>
      <text class="desc" v-if="t.description">{{ t.description }}</text>
      <text class="meta">余票 {{ t.remaining ?? t.quota }} / 总量 {{ t.quota }}</text>
      <button class="btn" size="mini" :disabled="t.remaining === 0" @click="buy(t)">立即购买</button>
    </view>
    <view v-if="!types.length && loaded" class="empty">该展会暂无票种（主办方可到「票种管理」添加）</view>

    <view class="result" v-if="lastTicket">
      <text class="ok">✅ 出票成功</text>
      <text class="meta">票号：{{ lastTicket.ticket_no }}</text>
      <text class="meta small" selectable>载荷：{{ qrJson }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ticketingApi } from '@/api/ticketing'
import { getToken } from '@/utils/request'

const exhibitionId = ref(0)
const title = ref('')
const types = ref<any[]>([])
const loaded = ref(false)
const lastTicket = ref<any>(null)
const qrJson = ref('')
const buying = ref(false)

onLoad((q: any) => {
  exhibitionId.value = Number(q?.exhibitionId || 0)
  title.value = q?.title ? decodeURIComponent(q.title) : ''
  loadTypes()
})

async function loadTypes() {
  try {
    const res: any = await ticketingApi.listTicketTypes(exhibitionId.value)
    types.value = res?.list || []
  } catch (e) {
    uni.showToast({ title: '加载票种失败', icon: 'none' })
  } finally {
    loaded.value = true
  }
}

async function buy(t: any) {
  if (buying.value) return
  if (!getToken()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.navigateTo({ url: '/pages/login/login' }), 600)
    return
  }
  buying.value = true
  try {
    const order: any = await ticketingApi.createOrder({ exhibition_id: exhibitionId.value, ticket_type_id: t.id })
    let ticket = order
    if (order.status === 'pending' && order.order_no) {
      uni.showLoading({ title: '模拟支付中' })
      ticket = await ticketingApi.payOrder(order.order_no)
      uni.hideLoading()
    }
    const t0 = ticket.tickets?.[0] || ticket.ticket || ticket
    lastTicket.value = t0
    qrJson.value = JSON.stringify({ t: t0.ticket_no, s: t0.signature })
    uni.showToast({ title: '购票成功', icon: 'success' })
  } catch (e: any) {
    uni.showToast({ title: e.message || '购票失败', icon: 'none' })
  } finally {
    buying.value = false
  }
}
</script>

<style scoped>
.page { padding: 16px; background: #f5f6f8; min-height: 100vh; }
.head { margin-bottom: 12px; }
.h { font-size: 18px; font-weight: 700; display: block; }
.sub { font-size: 12px; color: #999; display: block; margin-top: 4px; }
.card { background: #fff; border-radius: 10px; padding: 14px; margin-bottom: 10px; }
.row { display: flex; justify-content: space-between; align-items: center; }
.name { font-size: 16px; font-weight: 600; }
.price { color: #e5484d; font-weight: 700; }
.desc { display: block; font-size: 12px; color: #666; margin: 6px 0; }
.meta { display: block; font-size: 12px; color: #999; margin-top: 4px; }
.btn { margin-top: 10px; background: #4f6ef7; color: #fff; }
.result { background: #eaf7ef; border-radius: 10px; padding: 14px; margin-top: 14px; }
.ok { color: #2f9e5f; font-weight: 700; display: block; margin-bottom: 6px; }
.small { font-size: 10px; word-break: break-all; }
.empty { text-align: center; color: #999; padding: 40px 0; }
</style>
