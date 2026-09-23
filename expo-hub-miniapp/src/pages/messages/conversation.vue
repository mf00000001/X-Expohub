<template>
  <view class="chat-page">
    <view class="chat-header">
      <view class="back-btn" @click="goBack">
        <text class="back-arrow">←</text>
        <text class="back-text">返回</text>
      </view>
      <text class="chat-title">对话</text>
      <view class="chat-header-spacer"></view>
    </view>

    <scroll-view
      class="chat-messages"
      scroll-y
      :scroll-into-view="scrollIntoView"
      scroll-with-animation
    >
      <LoadingSkeleton v-if="loading" :lines="6" />
      <template v-else>
        <view v-if="messages.length === 0" class="text-center text-secondary chat-empty">
          <text>暂无消息</text>
        </view>
        <view
          v-for="msg in messages"
          :key="msg.id"
          :id="'msg-' + msg.id"
          :class="['message-row', isMine(msg) ? 'row-mine' : '']"
        >
          <view class="message-bubble">
            <view v-if="!isMine(msg)" class="message-sender text-sm text-secondary">
              <text>{{ msg.sender_name || '用户' }}</text>
            </view>
            <view class="message-content">
              <text>{{ msg.content }}</text>
            </view>
            <view class="message-time text-sm text-secondary">
              <text>{{ msg.created_at }}</text>
            </view>
          </view>
        </view>
        <view id="msg-bottom" class="msg-bottom-anchor"></view>
      </template>
    </scroll-view>

    <view class="chat-input-area">
      <input cursor-spacing="24"
        v-model="newMessage"
        class="form-input chat-input"
        placeholder="输入消息..."
        confirm-type="send"
        :disabled="sending"
        @confirm="sendMessage"
      />
      <view
        class="btn btn-primary chat-send-btn"
        :class="{ 'btn-disabled': sending || !newMessage.trim() }"
        @click="sendMessage"
      >
        <text>{{ sending ? '发送中...' : '发送' }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import { messageApi, type Message } from '@/api/message'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const conversationId = ref(0)
const messages = ref<Message[]>([])
const loading = ref(true)
const newMessage = ref('')
const sending = ref(false)
const scrollIntoView = ref('')

onLoad((options) => {
  conversationId.value = Number(options?.id || 0)
  if (!conversationId.value) {
    uni.showToast({ title: '参数错误', icon: 'none' })
    setTimeout(() => goBack(), 500)
    return
  }
  init()
})

async function init() {
  await fetchMessages()
  try {
    await messageApi.markRead(conversationId.value)
  } catch {
    // 标记已读失败不阻塞聊天
  }
}

async function fetchMessages() {
  loading.value = true
  try {
    const res = (await messageApi.getMessages(conversationId.value)) as any
    messages.value = Array.isArray(res)
      ? (res as Message[])
      : res.list || res.items || res.results || []
    await nextTick()
    scrollToBottom()
  } catch (err) {
    console.error('Failed to load messages:', err)
    uni.showToast({ title: (err as Error).message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function sendMessage() {
  const content = newMessage.value.trim()
  if (!content || sending.value) return
  sending.value = true
  try {
    const msg = await messageApi.sendMessage(conversationId.value, content)
    newMessage.value = ''
    if (msg && msg.id) {
      messages.value.push(msg)
    } else {
      await fetchMessages()
    }
    await nextTick()
    scrollToBottom()
  } catch (err) {
    console.error('Failed to send message:', err)
    uni.showToast({ title: (err as Error).message || '发送失败', icon: 'none' })
  } finally {
    sending.value = false
  }
}

function isMine(msg: Message) {
  return msg.sender_id === userStore.profile?.id
}

async function scrollToBottom() {
  // 先清空再设置，确保每次值变化都能触发 scroll-into-view
  scrollIntoView.value = ''
  await nextTick()
  scrollIntoView.value = 'msg-bottom'
}

function goBack() {
  uni.navigateBack()
}
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--color-bg);
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid var(--color-border);
}
.back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--color-primary);
  padding: 4px 0;
}
.back-arrow {
  font-size: 16px;
}
.back-text {
  font-size: 14px;
}
.chat-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
}
.chat-header-spacer {
  width: 48px;
}
.chat-messages {
  flex: 1;
  height: 0;
  min-height: 0;
  padding: 16px 16px 0;
  box-sizing: border-box;
}
.chat-empty {
  padding: 48px 0;
}
.message-row {
  display: flex;
  margin-bottom: 16px;
}
.row-mine {
  justify-content: flex-end;
}
.message-bubble {
  max-width: 70%;
}
.row-mine .message-bubble {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.message-sender {
  margin-bottom: 4px;
}
.message-content {
  display: inline-block;
  padding: 10px 16px;
  border-radius: 16px;
  background: #fff;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-all;
}
.row-mine .message-content {
  background: var(--color-primary);
  color: #fff;
}
.message-time {
  margin-top: 4px;
}
.msg-bottom-anchor {
  height: 4rpx;
}
.chat-input-area {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  padding-bottom: calc(12px + constant(safe-area-inset-bottom));
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: #fff;
  border-top: 1px solid var(--color-border);
}
.chat-input {
  flex: 1;
}
.chat-send-btn {
  flex-shrink: 0;
}
</style>
