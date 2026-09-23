<script setup lang="ts">
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const username = ref('')
const password = ref('')
const loading = ref(false)

async function handleLogin() {
  if (loading.value) return
  if (!username.value || !password.value) {
    uni.showToast({ title: '请输入用户名和密码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    await userStore.login(username.value, password.value)
    uni.switchTab({ url: '/pages/index/index' })
  } catch (err: any) {
    uni.showToast({ title: err?.message || '登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function handleWechatLogin() {
  if (loading.value) return
  loading.value = true
  try {
    const loginRes = await new Promise<{ code?: string }>((resolve, reject) => {
      uni.login({
        provider: 'weixin',
        success: resolve,
        fail: reject,
      })
    })
    if (!loginRes.code) {
      uni.showToast({ title: '未获取到登录凭证', icon: 'none' })
      return
    }
    await userStore.wechatLogin(loginRes.code)
    uni.switchTab({ url: '/pages/index/index' })
  } catch (err: any) {
    uni.showToast({ title: err?.message || '微信登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function goToRegister() {
  uni.navigateTo({ url: '/pages/auth/register' })
}
</script>

<template>
  <view class="auth-page">
    <view class="auth-card card">
      <view class="card-body">
        <text class="auth-title">登录 ExpoHub</text>

        <view class="form-group">
          <text class="form-label">用户名</text>
          <input cursor-spacing="24"
            v-model="username"
            class="form-input"
            type="text"
            placeholder="请输入用户名"
            confirm-type="next"
          />
        </view>

        <view class="form-group">
          <text class="form-label">密码</text>
          <input cursor-spacing="24"
            v-model="password"
            class="form-input"
            type="password"
            placeholder="请输入密码"
            confirm-type="done"
            @confirm="handleLogin"
          />
        </view>

        <view
          class="btn btn-primary btn-block btn-lg"
          :class="{ 'btn-disabled': loading }"
          @click="handleLogin"
        >
          <text>{{ loading ? '登录中...' : '登录' }}</text>
        </view>

        <view class="divider-line">
          <view class="line"></view>
          <text class="divider-text">或</text>
          <view class="line"></view>
        </view>

        <view class="btn btn-outline btn-block btn-lg" @click="handleWechatLogin">
          <text>💚 微信一键登录</text>
        </view>

        <view class="auth-footer">
          <text class="text-secondary">没有账号?</text>
          <text class="auth-link" @click="goToRegister">去注册</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40rpx;
  box-sizing: border-box;
  background: var(--color-bg);
}

.auth-card {
  width: 100%;
  max-width: 460px;
}

.auth-title {
  display: block;
  text-align: center;
  font-size: 44rpx;
  font-weight: 700;
  margin-bottom: 48rpx;
}

.divider-line {
  display: flex;
  align-items: center;
  margin: 32rpx 0;
}

.line {
  flex: 1;
  height: 1px;
  background: var(--color-border);
}

.divider-text {
  padding: 0 16rpx;
  font-size: 24rpx;
  color: var(--color-text-secondary);
}

.auth-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 32rpx;
  font-size: 28rpx;
}

.auth-link {
  color: var(--color-primary);
  margin-left: 8rpx;
}
</style>
