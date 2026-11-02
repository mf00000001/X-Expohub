<script setup lang="ts">
import { ref, computed } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

// 2026-10-19 起后端取消「主办方」角色，自助注册仅开放 游客/买家/展商
const roleOptions = [
  { value: 'visitor', label: '🏃 游客 — 浏览展会信息' },
  { value: 'buyer', label: '🛒 买家 — 报名展会 & 发布采购需求' },
  { value: 'exhibitor', label: '🏢 展商 — 管理展位 & 展示展品' },
]

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const role = ref('buyer')
// 展商资质（选填）：仅角色为展商时展示并提交
const companyName = ref('')
const businessLicense = ref('')
const loading = ref(false)
// 隐私确认弹窗是否开启中：弹窗期间禁用注册按钮，避免重复点击弹出多个 modal
const pendingModal = ref(false)

const roleIndex = computed(() => {
  const idx = roleOptions.findIndex((o) => o.value === role.value)
  return idx === -1 ? 0 : idx
})

function onRoleChange(e: { detail: { value: string | number } }) {
  role.value = roleOptions[Number(e.detail.value)].value
}

// 合规：后端强制要求 privacy_agreed=true，故提交前弹窗确认（小程序暂不做协议页面）
function confirmPrivacy(): Promise<boolean> {
  // 弹窗开启期间置位，按钮同步禁用，避免重复弹出多个 modal
  pendingModal.value = true
  return new Promise((resolve) => {
    uni.showModal({
      title: '用户协议与隐私政策',
      content: '请确认已阅读并同意《用户协议》与《隐私政策》',
      confirmText: '同意并注册',
      cancelText: '取消',
      success: (res) => resolve(!!res.confirm),
      fail: () => resolve(false),
      complete: () => {
        // 弹窗关闭后复位
        pendingModal.value = false
      },
    })
  })
}

async function handleRegister() {
  // 弹窗未关闭或正在提交时直接忽略，避免重复弹窗 / 重复提交
  if (loading.value || pendingModal.value) return
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

  const agreed = await confirmPrivacy()
  if (!agreed) return

  // 展商资质为选填：仅展商提交，空值统一传 undefined（不传空字符串）
  const isExhibitor = role.value === 'exhibitor'
  const data = {
    username: username.value,
    email: email.value,
    password: password.value,
    role: role.value,
    privacy_agreed: true,
    company_name: isExhibitor ? companyName.value.trim() || undefined : undefined,
    business_license: isExhibitor ? businessLicense.value.trim() || undefined : undefined,
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

        <!-- 展商资质（选填）：仅角色为展商时展示，不校验必填 -->
        <view v-if="role === 'exhibitor'" class="exhibitor-fields">
          <view class="form-group">
            <text class="form-label">公司名称</text>
            <input cursor-spacing="24"
              v-model="companyName"
              class="form-input"
              type="text"
              placeholder="请输入公司名称（选填）"
            />
          </view>

          <view class="form-group">
            <text class="form-label">营业执照图片 URL</text>
            <input cursor-spacing="24"
              v-model="businessLicense"
              class="form-input"
              type="text"
              placeholder="请输入营业执照图片链接（选填）"
            />
          </view>

          <text class="exhibitor-hint">展商资质选填，不填不影响注册</text>
        </view>

        <view
          class="btn btn-primary btn-block btn-lg"
          :class="{ 'btn-disabled': loading || pendingModal }"
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

/* 展商资质分组：与上方角色选择保持固定间距（选填，仅展商可见） */
.exhibitor-fields {
  margin: 16rpx 0 8rpx;
}

.exhibitor-hint {
  display: block;
  margin-top: 8rpx;
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
