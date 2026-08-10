<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const profile = computed(() => userStore.profile)
const editing = ref(false)
const editForm = ref({
  email: '',
  phone: '',
  company: '',
})
const saving = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

function startEdit() {
  if (profile.value) {
    editForm.value = {
      email: profile.value.email || '',
      phone: profile.value.phone || '',
      company: profile.value.company || '',
    }
  }
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveProfile() {
  saving.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    await userStore.updateProfile(editForm.value)
    successMsg.value = '保存成功'
    editing.value = false
  } catch (err: any) {
    errorMsg.value = err?.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <NavBar />
    <div class="container page-wrapper">
      <h1 class="page-title">个人中心</h1>

      <div v-if="profile" class="card">
        <div class="card-header">
          <h2 class="font-semibold">个人信息</h2>
          <button v-if="!editing" class="btn btn-outline btn-sm" @click="startEdit">编辑</button>
        </div>
        <div class="card-body">
          <div v-if="successMsg" class="tag tag-green mb-4">{{ successMsg }}</div>
          <div v-if="errorMsg" class="form-error mb-4">{{ errorMsg }}</div>

          <div v-if="!editing">
            <div class="info-row">
              <span class="text-secondary">用户名：</span>
              <span>{{ profile.username }}</span>
            </div>
            <div class="info-row">
              <span class="text-secondary">邮箱：</span>
              <span>{{ profile.email || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="text-secondary">角色：</span>
              <span class="tag tag-blue">{{ profile.role }}</span>
            </div>
            <div class="info-row">
              <span class="text-secondary">手机：</span>
              <span>{{ profile.phone || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="text-secondary">公司：</span>
              <span>{{ profile.company || '-' }}</span>
            </div>
            <div class="info-row" v-if="profile.created_at">
              <span class="text-secondary">注册时间：</span>
              <span>{{ profile.created_at }}</span>
            </div>
          </div>

          <div v-else>
            <div class="form-group">
              <label class="form-label">邮箱</label>
              <input v-model="editForm.email" class="form-input" type="email" />
            </div>
            <div class="form-group">
              <label class="form-label">手机</label>
              <input v-model="editForm.phone" class="form-input" type="text" />
            </div>
            <div class="form-group">
              <label class="form-label">公司</label>
              <input v-model="editForm.company" class="form-input" type="text" />
            </div>
            <div class="flex gap-2">
              <button class="btn btn-primary" :disabled="saving" @click="saveProfile">
                {{ saving ? '保存中...' : '保存' }}
              </button>
              <button class="btn btn-outline" @click="cancelEdit">取消</button>
            </div>
          </div>
        </div>
      </div>

      <div class="card mt-4">
        <div class="card-body">
          <div class="flex gap-2 flex-wrap">
            <button v-if="profile?.role === 'exhibitor'" class="btn btn-outline" @click="router.push('/exhibitor/dashboard')">
              展商中心
            </button>
            <button v-if="profile?.role === 'organizer'" class="btn btn-outline" @click="router.push('/organizer/dashboard')">
              管理后台
            </button>
            <button class="btn btn-outline" @click="router.push('/visitor/registrations')">
              我的报名
            </button>
            <button class="btn btn-outline" @click="router.push('/visitor/procurements')">
              我的采购
            </button>
            <button class="btn btn-outline" @click="router.push('/settings')">
              账号设置
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.info-row {
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  gap: 12px;
  align-items: center;
}
.info-row:last-child {
  border-bottom: none;
}
</style>
