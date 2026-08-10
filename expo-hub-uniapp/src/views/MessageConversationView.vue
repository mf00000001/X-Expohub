<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
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

onMounted(async () => {
  await fetchMessages()
  try {
    await messageApi.markRead(Number(route.params.id))
  } catch {}
})

async function fetchMessages() {
  try {
    const res = await messageApi.getMessages(Number(route.params.id))
    messages.value = res.items || res.results || res.data || []
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
    <NavBar />
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
            <div class="message-time text-sm text-secondary mt-1">{{ msg.created_at }}</div>
          </div>
        </div>
        <LoadingSkeleton v-else :lines="4" />

        <div class="chat-input-area">
          <input
            v-model="newMessage"
            class="form-input"
            placeholder="输入消息..."
            @keyup.enter="sendMessage"
          />
          <button class="btn btn-primary" :disabled="sending" @click="sendMessage">
            {{ sending ? '发送中...' : '发送' }}
          </button>
        </div>
      </div>
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
