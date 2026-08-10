<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { register } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')

async function handleRegister() {
  error.value = ''

  if (!username.value || !email.value || !password.value) {
    error.value = '请填写所有字段'
    return
  }
  if (password.value.length < 6) {
    error.value = '密码至少需要6个字符'
    return
  }
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(email.value)) {
    error.value = '请输入有效的邮箱地址'
    return
  }

  loading.value = true
  try {
    const data = await register({
      username: username.value,
      email: email.value,
      password: password.value,
    })
    userStore.setAuth({
      access_token: data.access_token,
      user: data.user,
    })
    router.push('/')
  } catch (e: any) {
    error.value = e.message || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-md mx-auto space-y-6 animate-fade-in pt-4">
    <div class="text-center">
      <div class="text-5xl mb-3">🌟</div>
      <h1 class="text-2xl font-bold text-gray-800">创建账号</h1>
      <p class="text-sm text-gray-500 mt-1">注册天气查询账号</p>
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
        />
      </div>

      <!-- 邮箱 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
        <input
          v-model="email"
          type="email"
          placeholder="请输入邮箱"
          class="input-field"
        />
      </div>

      <!-- 密码 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">密码</label>
        <input
          v-model="password"
          type="password"
          placeholder="至少6个字符"
          class="input-field"
        />
      </div>

      <!-- 确认密码 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">确认密码</label>
        <input
          v-model="confirmPassword"
          type="password"
          placeholder="再次输入密码"
          class="input-field"
          @keyup.enter="handleRegister"
        />
      </div>

      <!-- 注册按钮 -->
      <button
        @click="handleRegister"
        :disabled="loading"
        class="btn-primary w-full !py-3"
      >
        <span v-if="loading" class="animate-spin mr-2">⏳</span>
        {{ loading ? '注册中...' : '注册' }}
      </button>
    </div>

    <!-- 登录入口 -->
    <p class="text-center text-sm text-gray-500">
      已有账号？
      <RouterLink to="/login" class="text-blue-500 hover:text-blue-600 font-medium">
        立即登录
      </RouterLink>
    </p>
  </div>
</template>
