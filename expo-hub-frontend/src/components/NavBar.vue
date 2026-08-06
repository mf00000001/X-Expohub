<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useI18n } from '@/composables/useI18n'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { locale, toggleLocale } = useI18n()

const isLoggedIn = computed(() => userStore.isLoggedIn)
const userRole = computed(() => userStore.userRole)

function goTo(path: string) {
  router.push(path)
}

function handleLogout() {
  userStore.logout()
  router.push('/login')
}

const isHomeActive = computed(() => route.path === '/')
const isExhibitionsActive = computed(() => route.path.startsWith('/exhibitions'))
</script>

<template>
  <nav class="navbar">
    <div class="navbar-inner container">
      <div class="navbar-brand" @click="goTo('/')">
        <span class="brand-icon">🏪</span>
        <span class="brand-text">ExpoHub</span>
      </div>

      <div class="navbar-links">
        <a :class="{ active: isHomeActive }" @click="goTo('/')">展会市场</a>
        <a :class="{ active: isExhibitionsActive }" @click="goTo('/exhibitions')">全部展会</a>
        <a @click="goTo('/products')">展品</a>
        <a @click="goTo('/procurements')">采购</a>
        <a @click="goTo('/search')">搜索</a>
      </div>

      <div class="navbar-actions">
        <button class="lang-toggle" @click="toggleLocale" :title="locale === 'zh' ? 'Switch to English' : '切换中文'">
          {{ locale === 'zh' ? 'EN' : '中' }}
        </button>
        <template v-if="isLoggedIn">
          <a v-if="userRole === 'exhibitor'" @click="goTo('/exhibitor/dashboard')">展商中心</a>
          <a v-if="userRole === 'organizer'" @click="goTo('/organizer/dashboard')">管理后台</a>
          <a @click="goTo('/messages')" class="msg-link">📬 消息</a>
          <a @click="goTo('/profile')">个人中心</a>
          <button class="btn btn-sm btn-outline" @click="handleLogout">退出</button>
        </template>
        <template v-else>
          <button class="btn btn-sm btn-outline" @click="goTo('/login')">登录</button>
          <button class="btn btn-sm btn-primary" @click="goTo('/register')">注册</button>
        </template>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.navbar {
  background: var(--color-white);
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow-sm);
}

.navbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
}

.navbar-brand {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-icon {
  font-size: 22px;
}

.brand-text {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary);
}

.navbar-links {
  display: flex;
  align-items: center;
  gap: 4px;
}

.navbar-links a {
  padding: 8px 14px;
  border-radius: var(--radius);
  color: var(--color-text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.navbar-links a:hover,
.navbar-links a.active {
  color: var(--color-primary);
  background: #eff6ff;
}

.navbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.navbar-actions a {
  padding: 8px 12px;
  border-radius: var(--radius);
  color: var(--color-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.navbar-actions a:hover {
  color: var(--color-primary);
}

.msg-link {
  font-size: 15px;
}

.lang-toggle {
  padding: 4px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-white);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  color: var(--color-text-secondary);
  transition: all 0.15s;
}
.lang-toggle:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

@media (max-width: 768px) {
  .navbar-links {
    display: none;
  }
}
</style>
