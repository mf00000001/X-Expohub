<script setup lang="ts">
import { ref, computed } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const roleOptions = [
  { value: 'visitor', label: '🏃 游客 — 浏览展会信息' },
  { value: 'buyer', label: '🛒 买家 — 报名展会 & 发布采购需求' },
  { value: 'exhibitor', label: '🏢 展商 — 管理展位 & 展示展品' },
  { value: 'organizer', label: '🎪 主办方 — 创建展会 & 管理报名' },
]

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const role = ref('buyer')
const companyName = ref('')
const businessLicense = ref('')
const loading = ref(false)

const roleIndex = computed(() => {
  const idx = roleOptions.findIndex((o) => o.value === role.value)
  return idx === -1 ? 0 : idx
})

const isOrganizer = computed(() => role.value === 'organizer')

function onRoleChange(e: { detail: { value: string | number } }) {
  role.value = roleOptions[Number(e.detail.value)].value
}

async function handleRegister() {
  if (loading.value) return
  if (!username.value || !email.value || !password.value) {
    uni.showToast({ title: '请填写所有必填字段', icon: 'none' })
    return
  }
  if (password.value.length < 6) {
    uni.showToast({ title: '密码至少需要6个字符', icon: 'none' })
    return
  }
  if (password.value !== confirmPassword.value) {
    uni.showToast({ title: '两次输入的密码不一致', icon: 'none' })
    return
  }

  const data: {
    username: string
    email: string
    password: string
    role: string
    company_name?: string
    business_license?: string
  } = {
    username: username.value,
    email: email.value,
    password: password.value,
    role: role.value,
  }

  if (isOrganizer.value) {
    if (companyName.value.trim()) data.company_name = companyName.value.trim()
    if (businessLicense.value.trim()) data.business_license = businessLicense.value.trim()
  }

  loading.value = true
  try {
    await userStore.register(data)
    uni.switchTab({ url: '/pages/index/index' })
  } catch (err: any) {
    uni.showToast({ title: err?.message || '注册失败，请稍后再试', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function goToLogin() {
  uni.navigateTo({ url: '/pages/auth/login' })
}
</script>

<template>
  <view class="auth-page">
    <view class="auth-card card">
      <view class="card-body">
        <text class="auth-title">注册 ExpoHub</text>

        <view class="form-group">
          <text class="form-label">用户名 *</text>
          <input cursor-spacing="24" v-model="username" class="form-input" type="text" placeholder="请输入用户名" />
        </view>

        <view class="form-group">
          <text class="form-label">邮箱 *</text>
          <input cursor-spacing="24" v-model="email" class="form-input" type="text" placeholder="请输入邮箱" />
        </view>

        <view class="form-group">
          <text class="form-label">密码 *</text>
          <input cursor-spacing="24"
            v-model="password"
            class="form-input"
            type="password"
            placeholder="至少6个字符"
          />
        </view>

        <view class="form-group">
          <text class="form-label">确认密码 *</text>
          <input cursor-spacing="24"
            v-model="confirmPassword"
            class="form-input"
            type="password"
            placeholder="再次输入密码"
          />
        </view>

        <view class="form-group">
          <text class="form-label">选择角色 *</text>
          <picker :range="roleOptions" range-key="label" :value="roleIndex" @change="onRoleChange">
            <view class="picker-select">
              <text>{{ roleOptions[roleIndex].label }}</text>
              <text class="picker-arrow">▾</text>
            </view>
          </picker>
          <text class="role-hint">请选择适合您的角色，注册后可切换</text>
        </view>

        <view v-if="isOrganizer" class="organizer-fields">
          <view class="form-group">
            <text class="form-label">公司名称(选填)</text>
            <input cursor-spacing="24"
              v-model="companyName"
              class="form-input"
              type="text"
              placeholder="请输入公司名称"
            />
          </view>
          <view class="form-group">
            <text class="form-label">营业执照(选填)</text>
            <input cursor-spacing="24"
              v-model="businessLicense"
              class="form-input"
              type="text"
              placeholder="请输入营业执照号"
            />
          </view>
        </view>

        <view
          class="btn btn-primary btn-block btn-lg"
          :class="{ 'btn-disabled': loading }"
          @click="handleRegister"
        >
          <text>{{ loading ? '注册中...' : '注册' }}</text>
        </view>

        <view class="auth-footer">
          <text class="text-secondary">已有账号?</text>
          <text class="auth-link" @click="goToLogin">去登录</text>
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

.picker-select {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 14px;
  background: var(--color-white);
  box-sizing: border-box;
}

.picker-arrow {
  font-size: 24rpx;
  color: var(--color-text-secondary);
}

.role-hint {
  display: block;
  margin-top: 8rpx;
  font-size: 24rpx;
  color: var(--color-text-secondary);
}

.organizer-fields {
  margin-bottom: 8rpx;
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
