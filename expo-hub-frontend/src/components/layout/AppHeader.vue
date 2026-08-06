<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

import { ref, onMounted, watch } from 'vue'
import http from '@/api/index'

const isAuth = computed(() => userStore.isLoggedIn)
const role = computed(() => userStore.role || '')
const unreadNotif = ref(0)

async function fetchUnread() {
  if (!isAuth.value) return
  try { const r: any = await http.get('/notifications/unread-count'); unreadNotif.value = r?.data?.count || r?.count || 0 } catch {}
}
onMounted(fetchUnread)
watch(isAuth, (v) => { if (v) fetchUnread() })
setInterval(fetchUnread, 30000)  // poll every 30s

function go(path: string) { router.push(path) }
function goBack() { router.back() }
function goToLogin() { router.push('/login') }

const quickLinks = computed(() => {
  if (!isAuth.value) return []
  const links: {path:string;label:string;icon:string}[] = []
  if (role.value === 'exhibitor') {
    links.push({path:'/exhibitor/dashboard',label:'工作台',icon:'📊'})
    links.push({path:'/exhibitor/micro-booth',label:'微展位',icon:'🏪'})
  }
  if (role.value === 'buyer') {
    links.push({path:'/buyer/dashboard',label:'采购',icon:'📦'})
  }
  if (role.value === 'organizer' || role.value === 'admin') {
    links.push({path:'/organizer/dashboard',label:'管理',icon:'⚙️'})
  }
  links.push({path:'/points',label:'积分',icon:'💰'})
  links.push({path:'/messages',label:'消息',icon:'💬'})
  return links
})
</script>

<template>
  <header class="app-header">
    <div class="header-left">
      <button v-if="route.path !== '/'" class="back-btn" @click="goBack" aria-label="返回">←</button>
      <span v-else class="header-placeholder"></span>
    </div>

    <div class="header-center">
      <div class="header-search" @click="go('/search')">
        <span class="search-icon">🔍</span>
        <span class="search-hint">搜索展会、展商、展品...</span>
      </div>
    </div>

    <div class="header-right">
      <template v-if="isAuth">
        <div class="header-links">
          <button v-for="l in quickLinks" :key="l.path" class="hlink" @click="go(l.path)" :title="l.label">
            {{ l.icon }}
          </button>
          <button class="hlink notify-btn" @click="go('/notifications')" title="通知">
            🔔<span class="notify-badge" v-if="unreadNotif > 0">{{ unreadNotif > 99 ? '99+' : unreadNotif }}</span>
          </button>
        </div>
        <button class="user-btn" @click="go('/profile')">👤</button>
      </template>
      <button v-else class="login-btn" @click="goToLogin">登录</button>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position: fixed; top: 0; left: 0; right: 0; height: 48px;
  background: #fff; border-bottom: 1px solid var(--color-border-light);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 12px; z-index: 100;
}
.header-left, .header-right { display: flex; align-items: center; gap: 4px; min-width: 120px }
.header-right { justify-content: flex-end }
.header-center { flex: 1; text-align: center }
.header-title { font-size: 17px; font-weight: 700; color: var(--color-primary) }
.back-btn, .user-btn, .login-btn, .hlink { background: none; border: none; font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 6px; color: var(--color-text) }
.hlink { font-size: 16px; padding: 4px 6px }
.back-btn:hover, .hlink:hover { background: var(--color-bg-page) }
.login-btn { font-size: 13px; border: 1px solid var(--color-border); padding: 4px 12px }
.header-search { display:flex; align-items:center; gap:6px; padding:6px 12px; background:var(--color-bg-page); border-radius:20px; cursor:pointer; max-width:280px; margin:0 auto }
.search-icon { font-size:14px; flex-shrink:0 }
.search-hint { font-size:13px; color:var(--color-text-placeholder); overflow:hidden; white-space:nowrap; text-overflow:ellipsis }
.notify-btn { position:relative }
.notify-badge { position:absolute; top:-4px; right:-6px; background:#ef4444; color:#fff; font-size:10px; min-width:16px; height:16px; line-height:16px; text-align:center; border-radius:8px; padding:0 4px }
</style>
