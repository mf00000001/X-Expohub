<script setup lang="ts">
import { computed, ref } from 'vue'
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
  // 展商资质（选填）：2026-10-19 起仅展商保留，注册时没填的可以在这里补
  company_name: '',
  business_license: '',
})
const saving = ref(false)

// 当前登录用户资料（只读）：用于判断角色、回填展商资质字段
const profile = computed(() => userStore.profile)

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
      company_name: p.company_name || '',
      business_license: p.business_license || '',
    }
  }
})

async function saveProfile() {
  saving.value = true
  uni.showLoading({ title: '保存中' })
  try {
    // 展商资质为选填：仅展商提交，空值**直接删键**（不传 undefined、更不传空字符串）。
    // 后端用 model_dump(exclude_unset=True) 判断「哪些字段被显式设置」，
    // 依赖 JSON.stringify 丢弃 undefined 不够稳（不同端可能序列化成 null → 被当作显式写 null）。
    const isExhibitor = profile.value?.role === 'exhibitor'
    const payload: Record<string, any> = {
      nickname: form.value.nickname,
      phone: form.value.phone,
      company: form.value.company,
      position: form.value.position,
      bio: form.value.bio,
    }
    if (isExhibitor) {
      const cn = form.value.company_name.trim()
      const bl = form.value.business_license.trim()
      if (cn) payload.company_name = cn
      if (bl) payload.business_license = bl
    }
    const res = (await authApi.updateProfile(payload)) as Partial<UserProfile> & { success?: boolean }

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

        <!-- 展商资质（选填）：2026-10-19 起仅展商保留，注册时没填的在这里补，不校验必填与格式 -->
        <view v-if="profile && profile.role === 'exhibitor'">
          <view class="form-group">
            <text class="form-label">公司名称</text>
            <input cursor-spacing="24" v-model="form.company_name" class="form-input" placeholder="请输入公司名称（选填）" />
          </view>

          <view class="form-group">
            <text class="form-label">营业执照图片 URL</text>
            <input cursor-spacing="24" v-model="form.business_license" class="form-input" placeholder="请输入营业执照图片链接（选填）" />
          </view>
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
