<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

interface TabItem { path: string; label: string; icon: string; roles?: string[] }

const allTabs: TabItem[] = [
  { path: '/', label: '首页', icon: '🏠', roles: [] },
  { path: '/exhibitions', label: '展会', icon: '📋', roles: [] },
  { path: '/micro-booths', label: '微展位', icon: '🏪', roles: [] },
  { path: '/procurements', label: '采购', icon: '📦', roles: [] },
  // 展商
  { path: '/', label: '首页', icon: '🏠', roles: ['exhibitor'] },
  { path: '/exhibitor/dashboard', label: '工作台', icon: '📊', roles: ['exhibitor'] },
  { path: '/micro-booths', label: '广场', icon: '🏪', roles: ['exhibitor'] },
  { path: '/procurements', label: '采购', icon: '📋', roles: ['exhibitor'] },
  // 买家
  { path: '/', label: '首页', icon: '🏠', roles: ['buyer'] },
  { path: '/micro-booths', label: '微展位', icon: '🏪', roles: ['buyer'] },
  { path: '/buyer/dashboard', label: '采购', icon: '📦', roles: ['buyer'] },
  { path: '/favorites', label: '清单', icon: '📋', roles: ['buyer'] },
  // 游客/主办方/管理员
  { path: '/', label: '首页', icon: '🏠', roles: ['visitor','organizer','admin'] },
  { path: '/exhibitions', label: '展会', icon: '📋', roles: ['visitor','organizer','admin'] },
  { path: '/procurements', label: '采购需求', icon: '📦', roles: ['visitor','organizer','admin'] },
  { path: '/micro-booths', label: '微展位', icon: '🏪', roles: ['visitor','organizer','admin'] },
  { path: '/profile', label: '我的', icon: '👤', roles: ['visitor','organizer','admin'] },
]

const tabs = computed(() => {
  const role = userStore.role || ''
  const isAuth = userStore.isLoggedIn
  return allTabs.filter(t => {
    if (!t.roles) return false
    if (t.roles.length === 0) return !isAuth
    return isAuth && t.roles.includes(role)
  }).slice(0, 5)
})

const activeTab = computed(() => {
  const current = route.path
  const matched = tabs.value.find(t => current === t.path || (t.path !== '/' && current.startsWith(t.path)))
  return matched ? matched.path : '/'
})

function navigateTo(path: string) { router.push(path) }
</script>

<template>
  <nav class="app-footer">
    <button v-for="tab in tabs" :key="tab.path+tab.label" class="footer-tab"
            :class="{ active: activeTab === tab.path }" @click="navigateTo(tab.path)">
      <span class="tab-icon">{{ tab.icon }}</span>
      <span class="tab-label">{{ tab.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.app-footer { position:fixed;bottom:0;left:0;right:0;height:var(--footer-height);background:var(--bg-white);border-top:1px solid var(--border-color);display:flex;align-items:center;justify-content:space-around;z-index:100 }
.footer-tab { flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;background:none;border:none;cursor:pointer;padding:6px 0;color:var(--text-hint);transition:color .2s }
.footer-tab.active { color:var(--primary) }
.footer-tab:hover { color:var(--primary) }
.tab-icon { font-size:20px } .tab-label { font-size:11px }
</style>
