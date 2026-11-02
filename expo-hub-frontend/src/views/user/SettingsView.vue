<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi, type UserProfile } from "@/api/auth"
import http from "@/api/index"
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

// ============================================================
// 账号档案（含个性化推荐开关 / 兴趣标签 / 行业领域）
// ============================================================
const profile = ref<UserProfile | null>(null)
const loadingProfile = ref(false)
const profileError = ref('')

// 这两个值来自 profile，提前声明以便 loadProfile() 直接回填
const personalized = ref(true)   // 个性化推荐开关
const industryDomain = ref('')   // 行业领域（仅 exhibitor/admin 可见可改）

// 仅展商与管理员可设置行业领域（visitor/buyer 不再展示该分区，避免 403）
const canEditDomain = computed(() => ['exhibitor', 'admin'].includes(profile.value?.role || ''))

// 取后端错误文案：优先 detail（FastAPI 校验，可能是字符串或数组），其次 message（业务信封）
function pickError(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  const message = err?.response?.data?.message
  if (typeof message === 'string' && message) return message
  return fallback
}

async function loadProfile() {
  loadingProfile.value = true
  profileError.value = ''
  try {
    const p = await authApi.getProfile()
    profile.value = p
    personalized.value = p.personalized_recommend !== false
    industryDomain.value = p.industry_domain || ''
  } catch (err: any) {
    profileError.value = pickError(err, '加载账号信息失败，请刷新页面重试')
  } finally {
    loadingProfile.value = false
  }
}

// ============================================================
// 分区一：账户与安全（改密 + 退出登录）
// ============================================================
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changingPassword = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

async function changePassword() {
  errorMsg.value = ''
  successMsg.value = ''
  if (!oldPassword.value || !newPassword.value || !confirmPassword.value) {
    errorMsg.value = '请填写旧密码、新密码与确认新密码'
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
    errorMsg.value = pickError(err, '密码修改失败')
  } finally {
    changingPassword.value = false
  }
}

async function handleLogout() {
  // 先完成登出(含后端令牌撤销)再跳转,避免路由守卫误判"已登录访问登录页"而重定向到仪表盘
  await userStore.logout()
  router.push('/login')
}

// ============================================================
// 分区二：推荐与标签
// ============================================================
const prefSaving = ref(false)
const prefError = ref('')
const prefSuccess = ref('')

// 切换即落库：PUT /auth/preferences；失败回滚开关并提示
// 注意：直接读事件里的 checked，避免依赖 v-model 与 @change 的触发先后顺序
async function onPersonalizedChange(e: Event) {
  const next = (e.target as HTMLInputElement).checked
  personalized.value = next
  prefError.value = ''
  prefSuccess.value = ''
  prefSaving.value = true
  try {
    const res = await authApi.updatePreferences(next)
    // 以服务端返回值为准（避免本地状态与服务端不一致）
    personalized.value = res?.personalized_recommend !== false
    if (profile.value) profile.value.personalized_recommend = personalized.value
    prefSuccess.value = personalized.value
      ? '已开启个性化推荐'
      : '已关闭个性化推荐，推荐列表将按最新内容排序'
  } catch (err: any) {
    personalized.value = !next
    prefError.value = pickError(err, '个性化推荐设置失败，请稍后重试')
  } finally {
    prefSaving.value = false
  }
}

const interestList = computed<string[]>(() => {
  const raw = profile.value?.interests
  return Array.isArray(raw) ? raw.filter(Boolean) : []
})
// 逗号分隔展示；无标签时显示「未设置」
const interestText = computed(() => (interestList.value.length ? interestList.value.join('，') : '未设置'))

const clearingInterests = ref(false)
const interestsError = ref('')
const interestsSuccess = ref('')

// 清空标签：PUT /auth/interests {interests: []}，成功后刷新 profile
async function handleClearInterests() {
  interestsError.value = ''
  interestsSuccess.value = ''
  if (!interestList.value.length) {
    interestsError.value = '当前没有兴趣标签可清空'
    return
  }
  clearingInterests.value = true
  try {
    await authApi.clearInterests()
    await loadProfile()
    interestsSuccess.value = '兴趣标签已清空'
  } catch (err: any) {
    interestsError.value = pickError(err, '清空标签失败，请稍后重试')
  } finally {
    clearingInterests.value = false
  }
}

// ============================================================
// 分区三：行业领域（仅 exhibitor/admin）
// ============================================================
const savingDomain = ref(false)
const domainError = ref('')
const domainSuccess = ref('')

async function saveDomain() {
  domainError.value = ''
  domainSuccess.value = ''
  if (!industryDomain.value.trim()) {
    domainError.value = '请先填写行业领域'
    return
  }
  savingDomain.value = true
  try {
    await http.put('/exhibitors/domain', { industry_domain: industryDomain.value.trim() })
    if (profile.value) profile.value.industry_domain = industryDomain.value.trim()
    domainSuccess.value = '行业领域已保存'
  } catch (err: any) {
    domainError.value = pickError(err, '保存失败，请稍后重试')
  } finally {
    savingDomain.value = false
  }
}

onMounted(loadProfile)
</script>

<template>
  <div>
    <div class="container page-wrapper">
      <h1 class="page-title">账号设置</h1>

      <div v-if="profileError" class="form-error mb-sm">{{ profileError }}</div>

      <!-- ========== 分区一：账户与安全 ========== -->
      <section class="card settings-section">
        <h2 class="section-title">账户与安全</h2>
        <p class="section-desc">修改登录密码，或退出当前账号。</p>

        <div v-if="successMsg" class="tag tag-success mb-sm">{{ successMsg }}</div>
        <div v-if="errorMsg" class="form-error mb-sm">{{ errorMsg }}</div>

        <div class="form-group mb-sm">
          <label class="form-label" for="old-password">旧密码</label>
          <input id="old-password" v-model="oldPassword" class="form-input" type="password"
                 autocomplete="current-password" placeholder="请输入当前密码" />
        </div>
        <div class="form-group mb-sm">
          <label class="form-label" for="new-password">新密码</label>
          <input id="new-password" v-model="newPassword" class="form-input" type="password"
                 autocomplete="new-password" placeholder="至少6个字符" />
        </div>
        <div class="form-group mb-sm">
          <label class="form-label" for="confirm-password">确认新密码</label>
          <input id="confirm-password" v-model="confirmPassword" class="form-input" type="password"
                 autocomplete="new-password" placeholder="再次输入新密码" />
        </div>

        <div class="btn-row">
          <button class="btn btn-primary" :disabled="changingPassword" @click="changePassword">
            {{ changingPassword ? '修改中...' : '修改密码' }}
          </button>
          <button class="btn btn-outline btn-danger-text" @click="handleLogout">退出登录</button>
        </div>
      </section>

      <!-- ========== 分区二：推荐与标签 ========== -->
      <section class="card settings-section mt-lg">
        <h2 class="section-title">推荐与标签</h2>
        <p class="section-desc">
          关闭个性化推荐后，推荐与匹配结果将改为按最新内容排序，不再使用你的行业领域、兴趣标签等画像信息。
        </p>

        <div v-if="prefSuccess" class="tag tag-success mb-sm">{{ prefSuccess }}</div>
        <div v-if="prefError" class="form-error mb-sm">{{ prefError }}</div>
        <div v-if="interestsSuccess" class="tag tag-success mb-sm">{{ interestsSuccess }}</div>
        <div v-if="interestsError" class="form-error mb-sm">{{ interestsError }}</div>

        <div class="setting-row">
          <div class="setting-text">
            <div class="setting-label">个性化推荐</div>
            <div class="setting-hint">
              {{ personalized ? '已开启：按你的行业领域与兴趣标签排序' : '已关闭：按最新内容排序' }}
            </div>
          </div>
          <label class="switch">
            <input type="checkbox" v-model="personalized" :disabled="prefSaving || loadingProfile"
                   @change="onPersonalizedChange" />
            <span class="switch-slider"></span>
          </label>
        </div>

        <div class="setting-row">
          <div class="setting-text">
            <div class="setting-label">我的兴趣标签</div>
            <div class="setting-hint" :class="{ 'text-muted': !interestList.length }">{{ interestText }}</div>
          </div>
          <button class="btn btn-sm btn-outline" :disabled="clearingInterests || !interestList.length"
                  @click="handleClearInterests">
            {{ clearingInterests ? '清空中...' : '清空标签' }}
          </button>
        </div>
      </section>

      <!-- ========== 分区三：行业领域（仅展商 / 管理员） ========== -->
      <section v-if="canEditDomain" class="card settings-section mt-lg">
        <h2 class="section-title">行业领域</h2>
        <p class="section-desc">用于匹配采购需求，仅保留一份设置入口。</p>

        <div v-if="domainSuccess" class="tag tag-success mb-sm">{{ domainSuccess }}</div>
        <div v-if="domainError" class="form-error mb-sm">{{ domainError }}</div>

        <div class="form-group">
          <label class="form-label" for="industry-domain">行业领域</label>
          <input id="industry-domain" v-model="industryDomain" class="form-input" placeholder="如：电子及家电" />
        </div>
        <div class="btn-row">
          <button class="btn btn-sm btn-outline" :disabled="savingDomain" @click="saveDomain">
            {{ savingDomain ? '保存中...' : '保存行业领域' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-section {
  max-width: 720px;
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}
.section-desc {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  margin-bottom: 16px;
}
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
}
/* 仅在两行之间画分隔线（前面可能有提示条，不能用 :first-child） */
.setting-row + .setting-row {
  border-top: 1px solid var(--border-color, #e5e7eb);
}
.setting-text {
  min-width: 0;
}
.setting-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #111827);
}
.setting-hint {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  margin-top: 2px;
  word-break: break-word;
}
.setting-hint.text-muted {
  color: var(--text-tertiary, #9ca3af);
}
.btn-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
}
.btn-danger-text {
  color: var(--danger, #dc2626);
  border-color: var(--danger, #dc2626);
}

/* 开关 */
.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
  cursor: pointer;
}
.switch input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}
.switch-slider {
  position: absolute;
  inset: 0;
  background-color: #d1d5db;
  border-radius: 999px;
  transition: background-color 0.2s ease;
}
.switch-slider::before {
  content: "";
  position: absolute;
  width: 18px;
  height: 18px;
  left: 3px;
  top: 3px;
  background-color: #fff;
  border-radius: 50%;
  transition: transform 0.2s ease;
}
.switch input:checked + .switch-slider {
  background-color: var(--primary, #2563eb);
}
.switch input:checked + .switch-slider::before {
  transform: translateX(20px);
}
.switch input:disabled + .switch-slider {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
