<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { messageApi, type Conversation } from '@/api/message'
import { isLoggedIn } from '@/utils/auth'

const router = useRouter()
const conversations = ref<Conversation[]>([])
const loading = ref(true)
if (!isLoggedIn()) { loading.value = false }
const searchQuery = ref('')

const filteredConversations = computed(() => {
  if (!searchQuery.value.trim()) return conversations.value
  const q = searchQuery.value.trim().toLowerCase()
  return conversations.value.filter((c: any) => {
    const names = c.participants?.map((p: any) => p.username).join(' ').toLowerCase() || ''
    const lastMsg = c.last_message?.content?.toLowerCase() || ''
    return names.includes(q) || lastMsg.includes(q)
  })
})

function isOnline(conv: any): boolean {
  if (!conv.updated_at) return false
  const lastTime = new Date(conv.updated_at).getTime()
  return (Date.now() - lastTime) < 10 * 60 * 1000
}

onMounted(async () => {
  try {
    const res = await messageApi.getConversations()
    conversations.value = res.list || res.items || res.results || []
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
        <div class="container page-wrapper">
      <h1 class="page-title">消息</h1>

      <div style="margin-bottom:16px"><input v-model="searchQuery" class="form-input" placeholder="Search conversations..." style="width:100%" /></div>

      <LoadingSkeleton v-if="loading" :lines="5" />
      <EmptyState v-else-if="conversations.length === 0" message="暂无消息" icon="📬" />
      <div v-if="conversations.length > 0 && filteredConversations.length === 0" class="text-center text-secondary p-4">No matching conversations</div>
      <div v-else>
        <div
          v-for="conv in filteredConversations"
          :key="conv.id"
          class="card card-body mb-2 cursor-pointer"
          style="cursor:pointer"
          @click="goToConversation(conv.id)"
        >
          <div class="flex justify-between items-center" style="position:relative"><span v-if="isOnline(conv)" style="width:10px;height:10px;border-radius:50%;background:#67c23a;display:inline-block;margin-right:8px;flex-shrink:0" title="Online"></span>
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
