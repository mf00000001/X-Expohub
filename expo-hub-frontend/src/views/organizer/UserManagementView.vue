<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import StatusTag from '@/components/StatusTag.vue'
import http from '@/api/index'

const router = useRouter()

const users = ref<any[]>([])
const loading = ref(true)
const roleFilter = ref('exhibitor')

onMounted(() => {
  fetchUsers()
})

async function fetchUsers() {
  loading.value = true
  try {
    const res = await http.get('/admin/users', {
      params: { role: roleFilter.value || undefined },
    })
    users.value = res?.list || res?.results || []
  } catch (err) {
    console.error('Failed to load users:', err)
  } finally {
    loading.value = false
  }
}

async function approveUser(userId: number) {
  try {
    await http.patch(`/admin/users/${userId}/status`, null, {
      params: { organizer_status: 'approved' },
    })
    fetchUsers()
  } catch (err: any) {
    alert(err?.response?.data?.detail || 'Approve failed')
  }
}

async function rejectUser(userId: number) {
  if (!confirm('确认驳回？/ Confirm rejection?')) return
  try {
    await http.patch(`/admin/users/${userId}/status`, null, {
      params: { organizer_status: 'rejected' },
    })
    fetchUsers()
  } catch (err: any) {
    alert(err?.response?.data?.detail || 'Reject failed')
  }
}

function goToProfile(id: number) {
  router.push({ name: 'ExhibitorProfile', params: { id } })
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex justify-between items-center mb-6">
        <h1 class="page-title" style="margin-bottom:0">用户管理 / User Management</h1>
        <button class="btn btn-outline btn-sm" @click="router.push('/organizer/dashboard')">返回后台 / Back</button>
      </div>

      <div class="flex gap-4 mb-4" style="flex-wrap:wrap">
        <select v-model="roleFilter" class="form-select" style="width:200px" @change="fetchUsers">
          <option value="exhibitor">展商 / Exhibitors</option>
          <option value="organizer">主办方 / Organizers</option>
          <option value="">全部 / All</option>
        </select>
        <button class="btn btn-sm btn-outline" @click="fetchUsers">刷新 / Refresh</button>
      </div>

      <LoadingSkeleton v-if="loading" :lines="6" />
      <div v-else-if="users.length === 0" class="text-center text-secondary p-6">No users found / 暂无用户</div>
      <div v-else class="user-table-wrapper">
        <table class="user-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名 / Username</th>
              <th>公司 / Company</th>
              <th>角色 / Role</th>
              <th>状态 / Status</th>
              <th>操作 / Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.id }}</td>
              <td>
                <a href="#" class="user-link" @click.prevent="goToProfile(user.id)">{{ user.username }}</a>
              </td>
              <td>{{ user.company || user.company_name || '-' }}</td>
              <td><span class="tag tag-sm tag-info">{{ user.role }}</span></td>
              <td><StatusTag :status="user.organizer_status || user.status" /></td>
              <td>
                <div class="flex gap-2">
                  <button
                    v-if="user.organizer_status !== 'approved'"
                    class="btn btn-success btn-sm"
                    @click="approveUser(user.id)"
                  >通过 / Approve</button>
                  <button
                    v-if="user.organizer_status !== 'rejected'"
                    class="btn btn-danger btn-sm"
                    @click="rejectUser(user.id)"
                  >驳回 / Reject</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.user-table-wrapper { overflow-x: auto; }
.user-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-white);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
}
.user-table th, .user-table td {
  padding: 10px 14px;
  font-size: 14px;
  text-align: left;
  border-bottom: 1px solid var(--color-border-light);
}
.user-table th {
  background: var(--color-bg);
  font-weight: 600;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.user-link { color: var(--color-primary); cursor: pointer; text-decoration: none; }
.user-link:hover { text-decoration: underline; }
</style>
