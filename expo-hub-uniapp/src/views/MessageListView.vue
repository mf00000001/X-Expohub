<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { messageApi, type Conversation } from '@/api/message'

const router = useRouter()
const conversations = ref<Conversation[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await messageApi.getConversations()
    conversations.value = res.items || res.results || res.data || []
  } catch (err) {
    console.error('Failed to load conversations:', err)
  } finally {
    loading.value = false
  }
})

function goToConversation(id: number) {
  router.push({ name: 'message-conversation', params: { id } })
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <h1 class="page-title">消息</h1>

      <LoadingSkeleton v-if="loading" :lines="5" />
      <EmptyState v-else-if="conversations.length === 0" message="暂无消息" icon="📬" />
      <div v-else>
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="card card-body mb-2 cursor-pointer"
          style="cursor:pointer"
          @click="goToConversation(conv.id)"
        >
          <div class="flex justify-between items-center">
            <div>
              <span class="font-semibold">
                {{ conv.participants?.map((p) => p.username).join(', ') || '对话' }}
              </span>
              <p class="text-sm text-secondary mt-1">
                {{ conv.last_message?.content?.slice(0, 60) || '暂无消息' }}
              </p>
            </div>
            <div class="text-right">
              <span v-if="conv.unread_count > 0" class="unread-badge">{{ conv.unread_count }}</span>
              <p class="text-sm text-secondary mt-1">{{ conv.updated_at?.slice(0, 10) }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.unread-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-danger);
  color: #fff;
  border-radius: 50%;
  min-width: 22px;
  height: 22px;
  font-size: 12px;
  padding: 0 6px;
}
</style>
