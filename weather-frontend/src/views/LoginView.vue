<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { login } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  try {
    const data = await login({
      username: username.value,
      password: password.value,
    })
    userStore.setAuth({
      access_token: data.access_token,
      user: data.user,
    })
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: any) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-md mx-auto space-y-6 animate-fade-in pt-4">
    <div class="text-center">
      <div class="text-5xl mb-3">🌤️</div>
      <h1 class="text-2xl font-bold text-gray-800">欢迎回来</h1>
      <p class="text-sm text-gray-500 mt-1">登录您的天气查询账号</p>
    </div>

    <div class="card space-y-4">
      <!-- 错误提示 -->
      <div
        v-if="error"
        class="p-3 rounded-lg bg-red-50 text-red-600 text-sm animate-fade-in"
      >
        {{ error }}
      </div>

      <!-- 用户名 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
        <input
          v-model="username"
          type="text"
          placeholder="请输入用户名"
          class="input-field"
          @keyup.enter="handleLogin"
        />
      </div>

      <!-- 密码 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">密码</label>
        <input
          v-model="password"
          type="password"
          placeholder="请输入密码"
          class="input-field"
          @keyup.enter="handleLogin"
        />
      </div>

      <!-- 登录按钮 -->
      <button
        @click="handleLogin"
        :disabled="loading"
        class="btn-primary w-full !py-3"
      >
        <span v-if="loading" class="animate-spin mr-2">⏳</span>
        {{ loading ? '登录中...' : '登录' }}
      </button>
    </div>

    <!-- 注册入口 -->
    <p class="text-center text-sm text-gray-500">
      还没有账号？
      <RouterLink to="/register" class="text-blue-500 hover:text-blue-600 font-medium">
        立即注册
      </RouterLink>
    </p>
  </div>
</template>
