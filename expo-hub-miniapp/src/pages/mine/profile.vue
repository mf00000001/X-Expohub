<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { authApi, type UserProfile } from '@/api/auth'
import { useUserStore } from '@/stores/user'
import { requireLogin } from '@/utils/auth-guard'

const userStore = useUserStore()

const form = ref({
  nickname: '',
  phone: '',
  company: '',
  position: '',
  bio: '',
})
const saving = ref(false)

onLoad(() => {
  // 未登录跳登录页，避免表单提交时刷 401
  if (!requireLogin()) return
  const p = userStore.profile
  if (p) {
    form.value = {
      nickname: p.nickname || '',
      phone: p.phone || '',
      company: p.company || '',
      position: p.position || '',
      bio: p.bio || '',
    }
  }
})

async function saveProfile() {
  saving.value = true
  uni.showLoading({ title: '保存中' })
  try {
    const res = (await authApi.updateProfile({
      nickname: form.value.nickname,
      phone: form.value.phone,
      company: form.value.company,
      position: form.value.position,
      bio: form.value.bio,
    })) as Partial<UserProfile> & { success?: boolean }

    // 接口返回完整资料则直接更新 store，否则重新拉取
    if (res && typeof res === 'object' && 'id' in res) {
      userStore.profile = res as UserProfile
    } else {
      await userStore.fetchProfile()
    }

    uni.hideLoading()
    uni.showToast({ title: '保存成功', icon: 'success' })
    setTimeout(() => {
      uni.navigateBack()
    }, 500)
  } catch (err: any) {
    uni.hideLoading()
    uni.showToast({ title: err?.message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <view class="page-wrapper">
    <view class="card">
      <view class="card-body">
        <view class="form-group">
          <text class="form-label">昵称</text>
          <input cursor-spacing="24" v-model="form.nickname" class="form-input" placeholder="请输入昵称" />
        </view>

        <view class="form-group">
          <text class="form-label">手机号</text>
          <input cursor-spacing="24" v-model="form.phone" class="form-input" type="number" maxlength="11" placeholder="请输入手机号" />
        </view>

        <view class="form-group">
          <text class="form-label">公司</text>
          <input cursor-spacing="24" v-model="form.company" class="form-input" placeholder="请输入公司名称" />
        </view>

        <view class="form-group">
          <text class="form-label">职位</text>
          <input cursor-spacing="24" v-model="form.position" class="form-input" placeholder="请输入职位" />
        </view>

        <view class="form-group">
          <text class="form-label">简介</text>
          <textarea cursor-spacing="24" v-model="form.bio" class="form-textarea" placeholder="请输入个人简介" />
        </view>

        <view
          class="btn btn-primary btn-block"
          :class="{ 'btn-disabled': saving }"
          @click="saveProfile"
        >
          {{ saving ? '保存中...' : '保存' }}
        </view>
      </view>
    </view>
  </view>
</template>
