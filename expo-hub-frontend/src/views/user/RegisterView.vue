<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const role = ref('visitor')
const loading = ref(false)
const errorMsg = ref('')

async function handleRegister() {
  errorMsg.value = ''
  if (!username.value || !email.value || !password.value) {
    errorMsg.value = '请填写所有必填字段'
    return
  }
  if (password.value !== confirmPassword.value) {
    errorMsg.value = '两次输入的密码不一致'
    return
  }
  if (password.value.length < 6) {
    errorMsg.value = '密码至少需要6个字符'
    return
  }
  loading.value = true
  try {
    await userStore.register({
      username: username.value,
      email: email.value,
      password: password.value,
      role: role.value,
    })
    // V2.9: 买家直接进微展位广场，展商/游客进引导
    if (role.value === 'buyer') { router.push('/micro-booths') }
    else { router.push({name:'onboarding'}) }
  } catch (err: any) {
    errorMsg.value = err?.response?.data?.detail || err?.response?.data?.message || '注册失败，请稍后再试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
        <div class="auth-page">
      <div class="auth-card card">
        <div class="card-body p-6">
          <h2 class="text-center text-2xl font-bold mb-6">注册 ExpoHub</h2>
          <div class="form-group">
            <label class="form-label">用户名 *</label>
            <input v-model="username" class="form-input" type="text" placeholder="请输入用户名" />
          </div>
          <div class="form-group">
            <label class="form-label">邮箱 *</label>
            <input v-model="email" class="form-input" type="email" placeholder="请输入邮箱" />
          </div>
          <div class="form-group">
            <label class="form-label">密码 *</label>
            <input v-model="password" class="form-input" type="password" placeholder="至少6个字符" />
          </div>
          <div class="form-group">
            <label class="form-label">确认密码 *</label>
            <input v-model="confirmPassword" class="form-input" type="password" placeholder="再次输入密码" />
          </div>
          <div class="form-group">
            <label class="form-label">选择角色 *</label>
            <select v-model="role" class="form-input">
              <option value="visitor">🏃 游客 — 浏览展会信息</option>
              <option value="buyer">🛒 买家 — 报名展会 & 发布采购需求</option>
              <option value="exhibitor">🏢 展商 — 管理展位 & 展示展品</option>
              <option value="organizer">🎪 主办方 — 创建展会 & 管理报名</option>
            </select>
            <p class="text-sm text-secondary mt-1">请选择适合您的角色，注册后可切换</p>
          </div>
          <p v-if="errorMsg" class="form-error mb-4">{{ errorMsg }}</p>
          <button class="btn btn-primary btn-block btn-lg" :disabled="loading" @click="handleRegister">
            {{ loading ? '注册中...' : '注册' }}
          </button>
          <p class="text-center text-sm text-secondary mt-4">
            已有账号？<router-link to="/login">立即登录</router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: calc(100vh - 56px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.auth-card {
  width: 100%;
  max-width: 460px;
}
</style>
