<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from "@/api/auth"
import http from "@/api/index"
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changingPassword = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

async function changePassword() {
  errorMsg.value = ''
  successMsg.value = ''
  if (!oldPassword.value || !newPassword.value) {
    errorMsg.value = '请填写所有字段'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    errorMsg.value = '两次输入的新密码不一致'
    return
  }
  if (newPassword.value.length < 6) {
    errorMsg.value = '新密码至少需要6个字符'
    return
  }
  changingPassword.value = true
  try {
    await authApi.changePassword({
      old_password: oldPassword.value,
      new_password: newPassword.value,
    })
    successMsg.value = '密码修改成功'
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (err: any) {
    errorMsg.value = err?.response?.data?.detail || '密码修改失败'
  } finally {
    changingPassword.value = false
  }
}

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <h1 class="page-title">账号设置</h1>

      <div class="card">
        <div class="card-header">
          <h2 class="font-semibold">修改密码</h2>
        </div>
        <div class="card-body">
          <div v-if="successMsg" class="tag tag-green mb-4">{{ successMsg }}</div>
          <div v-if="errorMsg" class="form-error mb-4">{{ errorMsg }}</div>

          <div class="form-group">
        <label>行业领域</label>
        <input v-model="industryDomain" class="form-input" placeholder="如：电子及家电" />
        <button class="btn btn-sm btn-primary-outline" @click="saveDomain" style="margin-top:4px">保存行业领域</button>
      </div>
      <div class="form-group">
            <label class="form-label">旧密码</label>
            <input v-model="oldPassword" class="form-input" type="password" />
          </div>
          <div class="form-group">
        <label>行业领域</label>
        <input v-model="industryDomain" class="form-input" placeholder="如：电子及家电" />
        <button class="btn btn-sm btn-primary-outline" @click="saveDomain" style="margin-top:4px">保存行业领域</button>
      </div>
      <div class="form-group">
            <label class="form-label">新密码</label>
            <input v-model="newPassword" class="form-input" type="password" placeholder="至少6个字符" />
          </div>
          <div class="form-group">
        <label>行业领域</label>
        <input v-model="industryDomain" class="form-input" placeholder="如：电子及家电" />
        <button class="btn btn-sm btn-primary-outline" @click="saveDomain" style="margin-top:4px">保存行业领域</button>
      </div>
      <div class="form-group">
            <label class="form-label">确认新密码</label>
            <input v-model="confirmPassword" class="form-input" type="password" />
          </div>
          <button class="btn btn-primary" :disabled="changingPassword" @click="changePassword">
            {{ changingPassword ? '修改中...' : '修改密码' }}
          </button>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-body">
          <button class="btn btn-danger btn-sm" @click="handleLogout">退出登录</button>
        </div>
      </div>
    </div>
  </div>
</template>
