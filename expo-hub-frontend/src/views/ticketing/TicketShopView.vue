<script setup lang="ts">
// 购票页：浏览票种 → 下单（免费直通 / 付费 Mock 支付）→ 出票
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ticketingApi, type TicketTypeItem, type TicketItem } from '@/api/ticketing'
import { isLoggedIn } from '@/utils/auth'

const route = useRoute()
const router = useRouter()
const exhibitionId = Number(route.params.id)

const types = ref<TicketTypeItem[]>([])
const loading = ref(false)
const busy = ref(false)
const message = ref('')
const lastTicket = ref<TicketItem | null>(null)
const lastOrderNo = ref('')

async function load() {
  loading.value = true
  try {
    const res = await ticketingApi.listTicketTypes(exhibitionId)
    types.value = res.list || []
  } catch (e: any) {
    message.value = e?.response?.data?.message || '加载票种失败'
  } finally {
    loading.value = false
  }
}

function yuan(c: number): string {
  return c === 0 ? '免费' : `¥${(c / 100).toFixed(2)}`
}

async function buy(tt: TicketTypeItem) {
  message.value = ''
  lastTicket.value = null
  if (!isLoggedIn()) {
    router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  busy.value = true
  try {
    const order = await ticketingApi.createOrder({ exhibition_id: exhibitionId, ticket_type_id: tt.id })
    lastOrderNo.value = order.order_no
    if (order.status === 'paid') {
      const mine = await ticketingApi.myTickets()
      lastTicket.value = mine.list?.find((x) => x.exhibition_id === exhibitionId) || mine.list?.[0] || null
      message.value = '🎉 免费票购票成功，已出票'
      return
    }
    // 付费票：Mock 支付
    const paid = await ticketingApi.payOrder(order.order_no)
    message.value = '🎉 支付成功，已出票'
    const mine = await ticketingApi.myTickets()
    lastTicket.value = mine.list?.find((x) => x.ticket_no === paid.ticket_no) || null
  } catch (e: any) {
    message.value = e?.response?.data?.message || '下单失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="container main-content">
    <div class="flex justify-between items-center mb-md">
      <h2>🎫 购票 · 展会 #{{ exhibitionId }}</h2>
      <button class="btn btn-outline btn-sm" @click="router.push('/tickets/my')">我的票务</button>
    </div>

    <p v-if="message" class="form-error">{{ message }}</p>
    <p v-if="loading">加载中…</p>

    <div v-if="!loading && types.length === 0" class="card p-md form-error">
      该展会暂未设置可售票种
    </div>

    <div v-for="tt in types" :key="tt.id" class="card p-md mb-sm">
      <div class="flex justify-between items-center">
        <div>
          <div class="flex items-center gap-sm">
            <strong>{{ tt.name }}</strong>
            <span :class="tt.price_cents === 0 ? 'tag tag-success' : 'tag tag-warning'">{{ yuan(tt.price_cents) }}</span>
          </div>
          <div class="mt-sm" v-if="tt.description">{{ tt.description }}</div>
          <div class="mt-sm tag tag-info">余票 {{ tt.quota }}</div>
        </div>
        <button class="btn btn-primary" :disabled="busy" @click="buy(tt)">立即购买</button>
      </div>
    </div>

    <div v-if="lastTicket" class="card p-md mt-md">
      <h3>✅ 出票成功</h3>
      <div class="flex items-center gap-md flex-wrap">
        <div class="tag tag-success">票号 {{ lastTicket.ticket_no }}</div>
        <code class="tag tag-info" style="word-break: break-all">{{ lastTicket.qr_payload }}</code>
      </div>
      <p class="mt-sm">出示此载荷（票号+签名）给主办方核销，或在核销台输入。</p>
      <button class="btn btn-outline btn-sm mt-md" @click="router.push('/tickets/my')">查看我的票务</button>
    </div>
  </div>
</template>
