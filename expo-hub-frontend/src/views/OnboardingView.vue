<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import CategoryGrid from '@/components/CategoryGrid.vue'

const router = useRouter()
const selected = ref<string[]>([])
const saving = ref(false)
const errorMsg = ref('')

function toggleCategory(cat: string) {
  const idx = selected.value.indexOf(cat)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
  } else if (selected.value.length < 5) {
    selected.value.push(cat)
  }
}

async function saveAndGo() {
  if (selected.value.length === 0) {
    errorMsg.value = '请至少选择一个兴趣领域'
    return
  }
  saving.value = true
  errorMsg.value = ''
  try {
    await authApi.saveInterests(selected.value)
    router.push('/')
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.message || '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

function skip() {
  router.push('/')
}
</script>

<template>
  <div class="onboard-page">
    <div class="onboard-card">
      <div class="onboard-header">
        <span class="onboard-emoji">🎯</span>
        <h1>选择你感兴趣的领域</h1>
        <p>我们将根据你的兴趣推荐相关展会和展商</p>
      </div>

      <div class="selected-tags" v-if="selected.length > 0">
        <span class="stag" v-for="s in selected" :key="s">{{ s }} <button @click="toggleCategory(s)">×</button></span>
      </div>

      <CategoryGrid :active="selected" @select="toggleCategory" />

      <p v-if="errorMsg" class="onboard-error">{{ errorMsg }}</p>
      <p class="onboard-count">已选 {{ selected.length }}/5 个领域</p>

      <div class="onboard-actions">
        <button class="btn btn-default" @click="skip">跳过</button>
        <button class="btn btn-primary btn-lg" :disabled="saving" @click="saveAndGo">
          {{ saving ? '保存中...' : '保存并进入' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.onboard-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  padding: 24px; background: linear-gradient(135deg, #f0f4ff 0%, #e8ecf8 100%);
}
.onboard-card {
  background: #fff; border-radius: 20px; padding: 40px; max-width: 800px; width: 100%;
  box-shadow: 0 20px 60px rgba(0,0,0,0.08);
}
.onboard-header { text-align: center; margin-bottom: 28px; }
.onboard-emoji { font-size: 48px; display: block; margin-bottom: 12px; }
.onboard-header h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
.onboard-header p { color: var(--color-text-secondary); font-size: 15px; }
.selected-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; justify-content: center; }
.stag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 12px; background: var(--color-primary-light); color: var(--color-primary);
  border-radius: 20px; font-size: 13px; font-weight: 500;
}
.stag button { background: none; border: none; color: var(--color-primary); cursor: pointer; font-size: 16px; line-height: 1; }
.onboard-error { color: var(--color-danger); text-align: center; margin: 12px 0; font-size: 14px; }
.onboard-count { text-align: center; color: var(--color-text-secondary); font-size: 13px; margin: 16px 0; }
.onboard-actions { display: flex; justify-content: center; gap: 16px; margin-top: 24px; }
</style>
