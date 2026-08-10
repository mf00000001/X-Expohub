<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import NavBar from '@/components/NavBar.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  if (!username.value || !password.value) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  errorMsg.value = ''
  loading.value = true
  try {
    await userStore.login(username.value, password.value)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (err: any) {
    errorMsg.value = err?.response?.data?.detail || err?.response?.data?.message || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <NavBar />
    <div class="auth-page">
      <div class="auth-card card">
        <div class="card-body p-6">
          <h2 class="text-center text-2xl font-bold mb-6">登录 ExpoHub</h2>
          <div class="form-group">
            <label class="form-label">用户名</label>
            <input
              v-model="username"
              class="form-input"
              type="text"
              placeholder="请输入用户名"
              @keyup.enter="handleLogin"
            />
          </div>
          <div class="form-group">
            <label class="form-label">密码</label>
            <input
              v-model="password"
              class="form-input"
              type="password"
              placeholder="请输入密码"
              @keyup.enter="handleLogin"
            />
          </div>
          <p v-if="errorMsg" class="form-error mb-4">{{ errorMsg }}</p>
          <button class="btn btn-primary btn-block btn-lg" :disabled="loading" @click="handleLogin">
            {{ loading ? '登录中...' : '登录' }}
          </button>
          <p class="text-center text-sm text-secondary mt-4">
            还没有账号？<router-link to="/register">立即注册</router-link>
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
  max-width: 420px;
}
</style>
