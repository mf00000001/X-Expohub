<template>
  <view class="page">
    <text class="h">我的票务</text>

    <view class="sec">🎫 我的票券</view>
    <view class="card" v-for="t in tickets" :key="t.id">
      <view class="row">
        <text class="name">{{ t.ticket_type_name || '门票' }}</text>
        <text class="tag" :class="t.status">{{ statusText[t.status] || t.status }}</text>
      </view>
      <text class="meta" selectable>票号：{{ t.ticket_no }}</text>
      <text class="meta small" selectable>核销码：{{ JSON.stringify({ t: t.ticket_no, s: t.signature }) }}</text>
    </view>
    <view v-if="tickets.length === 0 && loaded" class="empty">暂无票券，去展会详情页购买</view>

    <view class="sec" style="margin-top: 20px">🧾 我的订单</view>
    <view class="card" v-for="o in orders" :key="o.id || o.order_no">
      <view class="row">
        <text class="name">{{ o.exhibition_title || ('订单 ' + (o.order_no || o.id)) }}</text>
        <text class="tag">{{ orderStatus[o.status] || o.status }}</text>
      </view>
      <text class="meta" v-if="o.order_no">单号：{{ o.order_no }}</text>
      <text class="meta">金额：¥{{ (o.total_cents ?? o.price_cents ?? 0) / 100 }}</text>
    </view>
    <view v-if="orders.length === 0 && loaded" class="empty">暂无订单</view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { ticketingApi } from '@/api/ticketing'

const tickets = ref<any[]>([])
const orders = ref<any[]>([])
const loaded = ref(false)
const statusText: Record<string, string> = { valid: '有效', used: '已核销', revoked: '已撤销', expired: '已过期' }
const orderStatus: Record<string, string> = { pending: '待支付', paid: '已支付', cancelled: '已取消' }

onShow(async () => {
  try {
    const [t, o] = await Promise.all([ticketingApi.myTickets(), ticketingApi.myOrders()])
    tickets.value = t?.list || t?.items || []
    orders.value = o?.list || o?.items || []
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loaded.value = true
  }
})
</script>

<style scoped>
.page { padding: 16px; background: #f5f6f8; min-height: 100vh; }
.h { font-size: 18px; font-weight: 700; display: block; margin-bottom: 6px; }
.sec { font-size: 14px; color: #333; font-weight: 600; margin: 10px 0 8px; }
.card { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 8px; }
.row { display: flex; justify-content: space-between; align-items: center; }
.name { font-size: 15px; font-weight: 600; }
.meta { display: block; font-size: 12px; color: #666; margin-top: 4px; }
.small { font-size: 10px; word-break: break-all; color: #999; }
.tag { font-size: 11px; padding: 2px 8px; border-radius: 8px; }
.tag.valid { background: #eaf7ef; color: #2f9e5f; }
.tag.used { background: #eef1fe; color: #4f6ef7; }
.tag.paid { background: #eaf7ef; color: #2f9e5f; }
.tag.pending { background: #fff3e0; color: #e6a23c; }
.empty { text-align: center; color: #999; padding: 30px 0; }
</style>
