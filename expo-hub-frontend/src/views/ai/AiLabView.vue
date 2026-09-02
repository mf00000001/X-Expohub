<script setup lang="ts">
// AI 实验室：调用平台 AI 能力（默认 mock 降级；配置密钥后走 DeepSeek/SiliconFlow）
import { onMounted, ref } from 'vue'
import { aiApi, type AiUsageItem } from '@/api/ai'

const capability = ref('qa')
const prompt = ref('帮我写一段展会撮合推荐理由')
const loading = ref(false)
const message = ref('')
const result = ref('')
const provider = ref('')
const degraded = ref(false)
const usage = ref<AiUsageItem[]>([])

const CAPS = [
  { value: 'qa', label: '大会答疑' },
  { value: 'reason', label: '撮合推荐理由' },
  { value: 'copy', label: '招展文案' },
  { value: 'generic', label: '通用' }
]

async function run() {
  message.value = ''
  result.value = ''
  loading.value = true
  try {
    const r = await aiApi.generate({ capability: capability.value, prompt: prompt.value })
    result.value = r.content
    provider.value = r.provider
    degraded.value = r.degraded
    await loadUsage()
  } catch (e: any) {
    message.value = e?.response?.data?.message || '调用失败'
  } finally {
    loading.value = false
  }
}

async function loadUsage() {
  try {
    const u = await aiApi.myUsage()
    usage.value = u.list || []
  } catch {
    usage.value = []
  }
}

onMounted(loadUsage)
</script>

<template>
  <div class="container main-content">
    <h2 class="mb-md">🤖 AI 实验室</h2>
    <p v-if="message" class="form-error">{{ message }}</p>

    <div class="card p-md mb-md">
      <div class="flex gap-md flex-wrap">
        <div>
          <label class="form-label">能力</label>
          <select v-model="capability" class="form-select">
            <option v-for="c in CAPS" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </div>
        <div class="flex-1">
          <label class="form-label">Prompt</label>
          <input v-model="prompt" class="form-input" />
        </div>
        <div class="flex items-end">
          <button class="btn btn-primary" :disabled="loading" @click="run">{{ loading ? '生成中…' : '生成' }}</button>
        </div>
      </div>

      <div v-if="result" class="card p-md mt-md">
        <div class="flex items-center gap-sm mb-sm">
          <span class="tag" :class="degraded ? 'tag-warning' : 'tag-success'">
            {{ provider }}{{ degraded ? '（降级/mock）' : '' }}
          </span>
        </div>
        <div class="form-textarea" style="white-space: pre-wrap">{{ result }}</div>
      </div>
    </div>

    <div class="card p-md">
      <h3 class="mb-sm">我的用量</h3>
      <div v-if="!usage.length" class="form-error">暂无调用记录</div>
      <div v-for="u in usage" :key="u.id" class="flex justify-between items-center mb-sm">
        <span><span class="tag tag-info mr-sm">{{ u.capability }}</span>{{ u.provider }}<span v-if="u.degraded">（降级）</span></span>
        <span class="tag">{{ u.prompt_chars }}字 → {{ u.response_chars }}字 · {{ u.cost_cents }}分</span>
      </div>
    </div>
  </div>
</template>
