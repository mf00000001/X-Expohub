<script setup lang="ts">
import { ref } from 'vue'
import { authApi } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changingPassword = ref(false)

async function changePassword() {
  if (!oldPassword.value || !newPassword.value || !confirmPassword.value) {
    uni.showToast({ title: '请填写所有字段', icon: 'none' })
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    uni.showToast({ title: '两次输入的新密码不一致', icon: 'none' })
    return
  }
  if (newPassword.value.length < 6) {
    uni.showToast({ title: '新密码至少需要6个字符', icon: 'none' })
    return
  }
  changingPassword.value = true
  uni.showLoading({ title: '修改中' })
  try {
    await authApi.changePassword({
      old_password: oldPassword.value,
      new_password: newPassword.value,
    })
    uni.hideLoading()
    uni.showToast({ title: '密码修改成功', icon: 'success' })
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (err: any) {
    uni.hideLoading()
    uni.showToast({ title: err?.message || '密码修改失败', icon: 'none' })
  } finally {
    changingPassword.value = false
  }
}

function handleLogout() {
  uni.showModal({
    title: '提示',
    content: '确定退出登录吗？',
    success: ({ confirm }) => {
      if (confirm) {
        userStore.logout()
        uni.showToast({ title: '已退出登录', icon: 'none' })
        setTimeout(() => {
          uni.switchTab({ url: '/pages/index/index' })
        }, 300)
      }
    },
  })
}
</script>

<template>
  <view class="page-wrapper">
    <view class="card">
      <view class="card-header">
        <text class="font-semibold">修改密码</text>
      </view>
      <view class="card-body">
        <view class="form-group">
          <text class="form-label">旧密码</text>
          <input cursor-spacing="24" v-model="oldPassword" class="form-input" type="password" placeholder="请输入旧密码" />
        </view>

        <view class="form-group">
          <text class="form-label">新密码</text>
          <input cursor-spacing="24" v-model="newPassword" class="form-input" type="password" placeholder="至少6个字符" />
        </view>

        <view class="form-group">
          <text class="form-label">确认新密码</text>
          <input cursor-spacing="24" v-model="confirmPassword" class="form-input" type="password" placeholder="再次输入新密码" />
        </view>

        <view
          class="btn btn-primary btn-block"
          :class="{ 'btn-disabled': changingPassword }"
          @click="changePassword"
        >
          {{ changingPassword ? '修改中...' : '修改密码' }}
        </view>
      </view>
    </view>

    <view class="card mt-4">
      <view class="card-body">
        <view class="btn btn-block logout-btn" @click="handleLogout">退出登录</view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.logout-btn {
  background: #fff;
  color: var(--color-danger);
  border: 1px solid var(--color-border);
}
</style>
