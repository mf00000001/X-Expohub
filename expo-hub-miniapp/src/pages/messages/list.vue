<template>
  <view class="page-wrapper">
    <LoadingSkeleton v-if="loading" :lines="5" />
    <view v-else-if="conversations.length === 0">
      <EmptyState
        :message="userStore.isLoggedIn ? '暂无消息' : '请先登录后查看消息'"
        :icon="userStore.isLoggedIn ? '📬' : '🔒'"
      />
      <view v-if="!userStore.isLoggedIn" class="btn btn-primary btn-block mt-4" @click="goLogin">去登录</view>
    </view>
    <view v-else>
      <view
        v-for="conv in conversations"
        :key="conv.id"
        class="card card-body mb-2 conv-card"
        @click="goToConversation(conv.id)"
      >
        <view class="flex justify-between items-center">
          <view class="flex-1 conv-main">
            <text class="font-semibold">{{ conversationTitle(conv) }}</text>
            <view class="text-sm text-secondary mt-1 ellipsis">
              <text>{{ conv.last_message?.content?.slice(0, 60) || '暂无消息' }}</text>
            </view>
          </view>
          <view class="text-right conv-side">
            <view v-if="(conv.unread_count || 0) > 0" class="unread-badge">
              <text>{{ conv.unread_count > 99 ? '99+' : conv.unread_count }}</text>
            </view>
            <view class="text-sm text-secondary mt-1">
              <text>{{ (conv.updated_at || '').slice(0, 10) }}</text>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import EmptyState from '@/components/EmptyState.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import { messageApi, type Conversation } from '@/api/message'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const conversations = ref<Conversation[]>([])
const loading = ref(true)

onShow(() => {
  // 未登录不发请求，避免 401 + NO_REFRESH_TOKEN 刷屏
  if (!userStore.isLoggedIn) {
    loading.value = false
    conversations.value = []
    return
  }
  fetchConversations()
})

async function fetchConversations() {
  loading.value = true
  try {
    const res = (await messageApi.getConversations({ page: 1, page_size: 50 })) as any
    conversations.value = Array.isArray(res)
      ? (res as Conversation[])
      : res.list || res.items || res.results || []
  } catch (err) {
    console.error('Failed to load conversations:', err)
    conversations.value = []
  } finally {
    loading.value = false
  }
}

// 展示对方用户名（过滤掉自己，1对1 场景即对方）
function conversationTitle(conv: Conversation) {
  const meId = userStore.profile?.id
  const peers = (conv.participants || [])
    .filter((p) => p.id !== meId)
    .map((p) => p.username)
  if (peers.length) return peers.join(', ')
  return (conv.participants || []).map((p) => p.username).join(', ') || '对话'
}

function goToConversation(id: number) {
  uni.navigateTo({ url: '/pages/messages/conversation?id=' + id })
}

function goLogin() {
  uni.navigateTo({ url: '/pages/auth/login' })
}
</script>

<style scoped>
.conv-card {
  overflow: hidden;
}
.conv-main {
  overflow: hidden;
}
.conv-side {
  flex-shrink: 0;
  margin-left: 12px;
}
.text-right {
  text-align: right;
}
.unread-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-danger);
  color: #fff;
  border-radius: 999rpx;
  min-width: 36rpx;
  height: 36rpx;
  padding: 0 12rpx;
  font-size: 22rpx;
  line-height: 1.2;
}
</style>
