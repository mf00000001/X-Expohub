<template>
  <view class="login-page">
    <view class="box">
      <text class="h">ExpoHub 登录</text>
      <input class="ipt" v-model="username" placeholder="用户名" />
      <input class="ipt" v-model="password" password placeholder="密码" />
      <button class="btn" :disabled="loading" @click="doLogin">{{ loading ? '登录中...' : '登 录' }}</button>
      <text class="tip">演示账号：buyer_li / buyer123 · organizer_canton / org123 · admin / admin123</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { request } from '@/utils/request'

const username = ref('')
const password = ref('')
const loading = ref(false)

async function doLogin() {
  if (!username.value || !password.value) {
    uni.showToast({ title: '请输入用户名和密码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const res: any = await request({
      url: '/auth/login',
      method: 'POST',
      data: { username: username.value, password: password.value },
      auth: false,
    })
    uni.setStorageSync('access_token', res.access_token)
    if (res.refresh_token) uni.setStorageSync('refresh_token', res.refresh_token)
    const u = res.user || {}
    uni.setStorageSync('expo_user', JSON.stringify({ id: u.id, username: u.username, role: u.role, company: u.company }))
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 500)
  } catch (e: any) {
    uni.showToast({ title: e.message || '登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { padding: 60px 32px; min-height: 100vh; background: #f5f6f8; }
.box { background: #fff; border-radius: 14px; padding: 28px 20px; }
.h { font-size: 20px; font-weight: 700; text-align: center; display: block; margin-bottom: 20px; }
.ipt { border: 1px solid #e0e2e8; border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-size: 15px; }
.btn { margin-top: 8px; background: #4f6ef7; color: #fff; border-radius: 8px; }
.tip { display: block; margin-top: 14px; font-size: 12px; color: #999; }
</style>
