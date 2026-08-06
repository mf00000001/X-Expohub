<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import { messageApi, type Message } from '@/api/message'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const userStore = useUserStore()
const messages = ref<Message[]>([])
const loading = ref(true)
const newMessage = ref('')
const sending = ref(false)
const chatContainer = ref<HTMLElement>()
const translatingId = ref<number | null>(null)
const otherTyping = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
let typingSendTimer: ReturnType<typeof setTimeout> | null = null
const showProductModal = ref(false)
const products = ref<any[]>([])
const loadingProducts = ref(false)

onMounted(async () => {
  await fetchMessages()
  try {
    await messageApi.markRead(Number(route.params.id))
  } catch {}
  loadProducts()
  pollTimer = setInterval(poll, 5000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (typingSendTimer) clearTimeout(typingSendTimer)
})

function formatTime(t: string) {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return 'just now'
  if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago'
  return d.toLocaleString()
}

async function translateMsg(msg: any) {
  if (translatingId.value === msg.id) return
  translatingId.value = msg.id
  try {
    const res: any = await messageApi.translate(msg.content, 'en')
    msg._translated = res?.translated ?? msg.content
  } catch { msg._translated = '[N/A]' }
  finally { translatingId.value = null }
}

async function checkTyping() {
  try { const res: any = await messageApi.getTypingStatus(Number(route.params.id)); otherTyping.value = res?.is_typing ?? false } catch {}
}

function onTyping() {
  if (typingSendTimer) clearTimeout(typingSendTimer)
  typingSendTimer = setTimeout(async () => { try { await messageApi.setTyping(Number(route.params.id)) } catch {} }, 200)
}

async function loadProducts() {
  loadingProducts.value = true
  try {
    const http = (await import('@/api/index')).default
    const resp: any = await http.get('/products', { params: { page_size: 50 } })
    products.value = resp?.list || resp?.items || resp?.results || (Array.isArray(resp) ? resp : [])
  } catch { products.value = [] }
  loadingProducts.value = false
}

function sendProduct(product: any) {
  newMessage.value = '[Product] ' + product.name
  showProductModal.value = false
}

async function poll() { await fetchMessages(); await checkTyping() }

async function fetchMessages() {
  try {
    const res = await messageApi.getMessages(Number(route.params.id))
    messages.value = res.list || res.items || res.results || []
    await nextTick()
    scrollToBottom()
  } catch (err) {
    console.error('Failed to load messages:', err)
  } finally {
    loading.value = false
  }
}

async function sendMessage() {
  if (!newMessage.value.trim() || sending.value) return
  sending.value = true
  try {
    await messageApi.sendMessage(Number(route.params.id), newMessage.value.trim())
    newMessage.value = ''
    await fetchMessages()
  } catch (err) {
    console.error('Failed to send message:', err)
  } finally {
    sending.value = false
  }
}

function scrollToBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}
</script>

<template>
  <div class="chat-page">
        <div class="container page-wrapper" style="flex:1;display:flex;flex-direction:column">
      <div class="breadcrumb">
        <router-link to="/messages">← 返回消息列表</router-link>
      </div>

      <div class="chat-box card" style="flex:1;display:flex;flex-direction:column">
        <div class="chat-messages" ref="chatContainer" v-if="!loading">
          <div v-if="messages.length === 0" class="text-center text-secondary p-6">暂无消息</div>
          <div
            v-for="msg in messages"
            :key="msg.id"
            :class="['message-bubble', msg.sender_id === userStore.profile?.id ? 'message-mine' : '']"
          >
            <div class="message-sender text-sm text-secondary mb-1">
              {{ msg.sender_name || '用户' }}
            </div>
            <div class="message-content">{{ msg.content }}</div>
            <button class="btn-translate" @click="translateMsg(msg)" :disabled="translatingId === msg.id" style="font-size:11px;background:none;border:1px solid #dcdfe6;border-radius:4px;padding:0 4px;cursor:pointer;color:#909399;margin-top:4px">{{ translatingId === msg.id ? '...' : 'A' }}</button>
            <div v-if="msg._translated" style="margin-top:4px;font-size:12px;color:#67c23a;border-left:2px solid #67c23a;padding-left:8px">{{ msg._translated }}</div>
            <div class="message-time text-sm text-secondary mt-1">{{ formatTime(msg.created_at) }}</div>
          </div>
        </div>
        <div v-if="otherTyping" style="font-size:12px;color:#909399;padding:4px 20px">typing...</div>
        <LoadingSkeleton v-else :lines="4" />

        <div class="chat-input-area">
          <button @click="showProductModal = true; loadProducts()" style="padding:8px 12px;background:#f5f7fa;border:1px solid #dcdfe6;border-radius:8px;cursor:pointer;font-size:13px;white-space:nowrap">+Product</button>
          <input
            v-model="newMessage"
            class="form-input"
            placeholder="输入消息..."
            @input="onTyping"
            @keyup.enter="sendMessage"
          />
          <button class="btn btn-primary" :disabled="sending" @click="sendMessage">
            {{ sending ? '发送中...' : '发送' }}
          </button>
        </div>
      </div>
    </div>
  </div>

<div class="modal-overlay" v-if="showProductModal" @click.self="showProductModal = false" style="position:fixed;inset:0;background:rgba(0,0,0,0.4);display:flex;justify-content:center;align-items:center;z-index:200">
  <div style="background:#fff;border-radius:12px;padding:28px;width:400px;max-height:70vh;overflow-y:auto">
    <h3>Share Product</h3>
    <div v-if="loadingProducts">Loading...</div>
    <div v-else-if="products.length === 0">No products</div>
    <div v-else>
      <div v-for="p in products" :key="p.id" @click="sendProduct(p)" style="padding:12px;border:1px solid #e4e7ed;border-radius:8px;cursor:pointer;margin-bottom:8px">
        <div style="font-weight:600">{{ p.name }}</div>
        <div style="font-size:12px;color:#909399"><span v-if="p.price">${{ p.price }}</span> <span v-if="p.category">{{ p.category }}</span></div>
      </div>
    </div>
    <div style="text-align:right;margin-top:20px"><button @click="showProductModal = false" style="padding:8px 20px;background:#f5f7fa;border:1px solid #dcdfe6;border-radius:6px;cursor:pointer">Cancel</button></div>
  </div>
</div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
.chat-box {
  flex: 1;
  max-height: calc(100vh - 180px);
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.message-bubble {
  margin-bottom: 16px;
  max-width: 70%;
}
.message-mine {
  margin-left: auto;
  text-align: right;
}
.message-content {
  display: inline-block;
  padding: 10px 16px;
  border-radius: 16px;
  background: #f3f4f6;
  font-size: 14px;
  line-height: 1.5;
}
.message-mine .message-content {
  background: var(--color-primary);
  color: #fff;
}
.chat-input-area {
  display: flex;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid var(--color-border);
}
.chat-input-area input {
  flex: 1;
}
</style>
