<script setup lang="ts">
// 我的票务：订单列表 + 有效入场券（含签名二维码载荷）
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ticketingApi, type OrderItem, type TicketItem } from '@/api/ticketing'
import { isLoggedIn } from '@/utils/auth'

const router = useRouter()
const loading = ref(false)
const orders = ref<OrderItem[]>([])
const tickets = ref<TicketItem[]>([])
const message = ref('')

async function load() {
  if (!isLoggedIn()) {
    router.push('/login')
    return
  }
  loading.value = true
  try {
    const [o, t] = await Promise.all([ticketingApi.myOrders(), ticketingApi.myTickets()])
    orders.value = o.list || []
    tickets.value = t.list || []
  } catch (e: any) {
    message.value = e?.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function statusTag(s: string): string {
  const map: Record<string, string> = { paid: 'tag-success', pending: 'tag-warning', cancelled: 'tag', refunded: 'tag-danger' }
  return map[s] || 'tag'
}

function statusText(s: string): string {
  const map: Record<string, string> = { paid: '已支付', pending: '待支付', cancelled: '已取消', refunded: '已退款' }
  return map[s] || s
}

function fen2yuan(c: number): string {
  return (c / 100).toFixed(2)
}

function goShop() {
  router.push('/exhibitions')
}

onMounted(load)
</script>

<template>
  <div class="container main-content">
    <div class="flex justify-between items-center mb-md">
      <h2>🎫 我的票务</h2>
      <button class="btn btn-outline btn-sm" @click="goShop">去购票</button>
    </div>

    <p v-if="message" class="form-error">{{ message }}</p>
    <p v-if="loading">加载中…</p>

    <div v-if="!loading" class="card p-md mb-md">
      <h3 class="mb-sm">有效入场券（{{ tickets.length }}）</h3>
      <div v-if="tickets.length === 0" class="form-error">暂无票券</div>
      <div v-for="t in tickets" :key="t.ticket_no" class="card p-md mb-sm">
        <div class="flex justify-between items-center">
          <div>
            <div><strong>{{ t.ticket_type_name }}</strong> · 展会 #{{ t.exhibition_id }}</div>
            <div class="tag tag-success">票号 {{ t.ticket_no }}</div>
          </div>
          <code class="tag tag-info" style="word-break: break-all">{{ t.qr_payload }}</code>
        </div>
      </div>
    </div>

    <div v-if="!loading" class="card p-md">
      <h3 class="mb-sm">订单（{{ orders.length }}）</h3>
      <div v-if="orders.length === 0" class="form-error">暂无订单</div>
      <div v-for="o in orders" :key="o.order_no" class="flex justify-between items-center mb-sm">
        <div>
          <span>{{ o.ticket_type_name }}</span>
          <span class="tag tag-info ml-sm">{{ o.order_no }}</span>
        </div>
        <div class="flex items-center gap-sm">
          <span>¥{{ fen2yuan(o.amount_cents) }}</span>
          <span :class="['tag', statusTag(o.status)]">{{ statusText(o.status) }}</span>
          <button
            v-if="o.status === 'pending'"
            class="btn btn-primary btn-sm"
            @click="router.push(`/exhibitions/${o.exhibition_id}/tickets`)"
          >去支付</button>
        </div>
      </div>
    </div>
  </div>
</template>
