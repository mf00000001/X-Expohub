<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const role = ref('visitor')
const loading = ref(false)
const errorMsg = ref('')
// 2026-10-19 合规：协议同意状态必须由用户主动勾选，默认不勾选
const privacyAgreed = ref(false)

async function handleRegister() {
  errorMsg.value = ''
  // 未勾选协议时一律不发请求（按钮已 disabled，这里再兜一层，防止回车/脚本触发）
  if (!privacyAgreed.value) {
    errorMsg.value = '请先阅读并同意《用户协议》与《隐私政策》'
    return
  }
  if (!username.value || !email.value || !password.value) {
    errorMsg.value = '请填写所有必填字段'
    return
  }
  if (password.value !== confirmPassword.value) {
    errorMsg.value = '两次输入的密码不一致'
    return
  }
  if (password.value.length < 6) {
    errorMsg.value = '密码至少需要6个字符'
    return
  }
  loading.value = true
  try {
    await userStore.register({
      username: username.value,
      email: email.value,
      password: password.value,
      role: role.value,
      // 勾选后固定传 true，后端据此写入隐私政策同意时间
      privacy_agreed: true,
    })
    // V2.9: 买家直接进微展位广场，展商/游客进引导
    if (role.value === 'buyer') { router.push('/micro-booths') }
    else { router.push({name:'onboarding'}) }
  } catch (err: any) {
    errorMsg.value = err?.response?.data?.detail || err?.response?.data?.message || '注册失败，请稍后再试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
        <div class="auth-page">
      <div class="auth-card card">
        <div class="card-body p-6">
          <h2 class="text-center text-2xl font-bold mb-6">注册 ExpoHub</h2>
          <div class="form-group">
            <label class="form-label">用户名 *</label>
            <input v-model="username" class="form-input" type="text" placeholder="请输入用户名" />
          </div>
          <div class="form-group">
            <label class="form-label">邮箱 *</label>
            <input v-model="email" class="form-input" type="email" placeholder="请输入邮箱" />
          </div>
          <div class="form-group">
            <label class="form-label">密码 *</label>
            <input v-model="password" class="form-input" type="password" placeholder="至少6个字符" />
          </div>
          <div class="form-group">
            <label class="form-label">确认密码 *</label>
            <input v-model="confirmPassword" class="form-input" type="password" placeholder="再次输入密码" />
          </div>
          <div class="form-group">
            <label class="form-label">选择角色 *</label>
            <select v-model="role" class="form-input">
              <option value="visitor">🏃 游客 — 浏览展会信息</option>
              <option value="buyer">🛒 买家 — 报名展会 & 发布采购需求</option>
              <option value="exhibitor">🏢 展商 — 管理展位 & 展示展品</option>
            </select>
            <p class="text-sm text-secondary mt-1">展会由平台运营；展商与采购商在此按身份注册</p>
          </div>
          <p v-if="errorMsg" class="form-error mb-4">{{ errorMsg }}</p>
          <!-- 2026-10-19 合规：协议同意（默认不勾选，两个书名号为可点击链接，新标签页打开） -->
          <div class="agree-row">
            <label class="agree-label">
              <input v-model="privacyAgreed" type="checkbox" class="agree-checkbox" />
              <span class="agree-text">
                我已阅读并同意
                <router-link to="/terms" target="_blank" rel="noopener" @click.stop>《用户协议》</router-link>
                与
                <router-link to="/privacy" target="_blank" rel="noopener" @click.stop>《隐私政策》</router-link>
              </span>
            </label>
            <p v-if="!privacyAgreed" class="agree-hint">请先勾选同意后再提交注册</p>
          </div>
          <button class="btn btn-primary btn-block btn-lg" :disabled="loading || !privacyAgreed" @click="handleRegister">
            {{ loading ? '注册中...' : '注册' }}
          </button>
          <p class="text-center text-sm text-secondary mt-4">
            已有账号？<router-link to="/login">立即登录</router-link>
          </p>
          <!-- 2026-10-19：平台自营说明（注册页底部小字） -->
          <p class="platform-note">平台为展会信息与撮合服务提供者；展会由平台运营。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: calc(100vh - 56px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.auth-card {
  width: 100%;
  max-width: 460px;
}
/* 2026-10-19 合规：协议勾选区 */
.agree-row {
  margin: 4px 0 16px;
}
.agree-label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}
.agree-checkbox {
  margin-top: 3px;
  width: 15px;
  height: 15px;
  flex: none;
  accent-color: var(--primary);
  cursor: pointer;
}
.agree-text a {
  color: var(--primary);
}
.agree-text a:hover {
  text-decoration: underline;
}
.agree-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}
.platform-note {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-color);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-hint);
  text-align: center;
}
</style>
