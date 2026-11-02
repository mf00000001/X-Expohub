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

// 后端历史审核状态字段：接口契约（查询参数名）不可改，故仅在此处集中保留英文键名
const APPROVAL_FIELD = 'organizer_status'

// 角色枚举 → 中文展示；未知值原样显示，避免丢信息
const ROLE_LABELS: Record<string, string> = {
  admin: '管理员',
  exhibitor: '展商',
  buyer: '买家',
  visitor: '观众',
}

function roleLabel(role: string): string {
  return ROLE_LABELS[role] || role || '-'
}

// 统一读取审核状态：优先取审核字段，缺失时回退到账号状态
function approvalStatus(user: any): string {
  return user[APPROVAL_FIELD] || user.status || ''
}

onMounted(() => {
  fetchUsers()
})

async function fetchUsers() {
  loading.value = true
  try {
    const res: any = await http.get('/admin/users', {
      params: { role: roleFilter.value || undefined },
    })
    users.value = res?.list || res?.results || []
  } catch (err) {
    console.error('加载用户列表失败：', err)
  } finally {
    loading.value = false
  }
}

async function approveUser(userId: number) {
  try {
    await http.patch(`/admin/users/${userId}/status`, null, {
      params: { [APPROVAL_FIELD]: 'approved' },
    })
    fetchUsers()
  } catch (err: any) {
    alert(err?.response?.data?.detail || '操作失败，请重试')
  }
}

async function rejectUser(userId: number) {
  if (!confirm('确认驳回该用户？')) return
  try {
    await http.patch(`/admin/users/${userId}/status`, null, {
      params: { [APPROVAL_FIELD]: 'rejected' },
    })
    fetchUsers()
  } catch (err: any) {
    alert(err?.response?.data?.detail || '操作失败，请重试')
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
        <h1 class="page-title" style="margin-bottom:0">用户管理</h1>
        <button class="btn btn-outline btn-sm" @click="router.push('/admin/dashboard')">返回后台</button>
      </div>

      <div class="flex gap-4 mb-4" style="flex-wrap:wrap">
        <select v-model="roleFilter" class="form-select" style="width:200px" @change="fetchUsers">
          <option value="exhibitor">展商</option>
          <option value="">全部</option>
        </select>
        <button class="btn btn-sm btn-outline" @click="fetchUsers">刷新</button>
      </div>

      <LoadingSkeleton v-if="loading" :lines="6" />
      <div v-else-if="users.length === 0" class="text-center text-secondary p-6">暂无用户</div>
      <div v-else class="user-table-wrapper">
        <table class="user-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>公司</th>
              <th>角色</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.id }}</td>
              <td>
                <a href="#" class="user-link" @click.prevent="goToProfile(user.id)">{{ user.username }}</a>
              </td>
              <td>{{ user.company || user.company_name || '-' }}</td>
              <td><span class="tag tag-sm tag-info">{{ roleLabel(user.role) }}</span></td>
              <td><StatusTag :status="approvalStatus(user)" /></td>
              <td>
                <div class="flex gap-2">
                  <button
                    v-if="approvalStatus(user) !== 'approved'"
                    class="btn btn-success btn-sm"
                    @click="approveUser(user.id)"
                  >通过</button>
                  <button
                    v-if="approvalStatus(user) !== 'rejected'"
                    class="btn btn-danger btn-sm"
                    @click="rejectUser(user.id)"
                  >驳回</button>
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
