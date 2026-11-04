<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import http from '@/api/index'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const isAuth = computed(() => userStore.isLoggedIn)
const role = computed(() => userStore.role || '')
const unreadNotif = ref(0)
const unreadMsg = ref(0)

async function fetchUnread() {
  if (!localStorage.getItem('access_token')) return
  try { const r: any = await http.get('/notifications/unread-count'); unreadNotif.value = r?.data?.count || r?.count || 0 } catch {}
  try { const m: any = await http.get('/messages/unread-count'); unreadMsg.value = m?.data?.count || m?.count || 0 } catch {}
}
onMounted(fetchUnread)
watch(isAuth, (v) => { if (v) fetchUnread() })
setInterval(fetchUnread, 30000)

function navTo(path: string) { router.push(path) }
function goBack() { if (route.path !== '/') { router.back() } else { router.push('/') } }
function goToLogin() { router.push('/login') }

/** 公开目录导航的选中态（展商名录 / 展品库） */
function isCatalogActive(section: 'products' | 'exhibitors'): boolean {
  return route.path === `/catalog/${section}` || route.path.startsWith(`/catalog/${section}/`)
}

const quickLinks = computed(() => {
  if (!isAuth.value) return []
  const links: {path:string;label:string;icon:string}[] = []
  if (role.value === 'exhibitor') {
    links.push({path:'/exhibitor/dashboard',label:'工作台',icon:'📊'})
    links.push({path:'/exhibitor/micro-booth',label:'微展位',icon:'🏪'})
    links.push({path:'/exhibitor/poster',label:'海报',icon:'📸'})
  }
  if (role.value === 'buyer') {
    links.push({path:'/buyer/dashboard',label:'采购',icon:'📦'})
    links.push({path:'/buyer/procurements/create',label:'发布',icon:'✍️'})
    links.push({path:'/favorites',label:'清单',icon:'📋'})
  }
  if (role.value === 'visitor') {
    links.push({path:'/visitor/procurements',label:'我的采购',icon:'📦'})
    links.push({path:'/points',label:'积分',icon:'💎'})
  }
  if (role.value === 'admin') {
    links.push({path:'/admin/dashboard',label:'管理',icon:'⚙️'})
    links.push({path:'/admin/exhibitions',label:'展会',icon:'🎪'})
  }
  if (role.value === 'admin') {
    links.push({path:'/admin/boss',label:'Boss',icon:'📊'})
  }
  links.push({path:'/profile',label:'我的',icon:'👤'})
  return links.slice(0, 7)
})
</script>

<template>
  <header class="app-header">
    <div class="header-left">
      <button v-if="route.path !== '/'" class="back-btn" @click="goBack">←</button>
      <span v-else class="header-placeholder"></span>
    </div>
    <div class="header-center">
      <span class="header-title" @click="navTo('/')">ExpoHub</span>
      <nav class="header-nav" aria-label="公开目录">
        <router-link
          class="header-nav-link"
          :class="{ 'is-active': route.path.startsWith('/expo-find') }"
          :to="{ name: 'expo-find' }"
        >找展</router-link>
        <router-link
          class="header-nav-link"
          :class="{ 'is-active': route.path.startsWith('/expo-intel') }"
          :to="{ name: 'expo-intel' }"
        >展会评估</router-link>
        <router-link
          class="header-nav-link"
          :class="{ 'is-active': isCatalogActive('exhibitors') }"
          :to="{ name: 'catalog-exhibitors' }"
        >展商名录</router-link>
        <router-link
          class="header-nav-link"
          :class="{ 'is-active': isCatalogActive('products') }"
          :to="{ name: 'catalog-products' }"
        >展品库</router-link>
      </nav>
    </div>
    <div class="header-right">
      <template v-if="isAuth">
        <div class="header-icons">
          <button v-for="l in quickLinks" :key="l.path" class="hicon" @click="navTo(l.path)">
            <span class="hi-icon">{{ l.icon }}</span>
            <span class="hi-label">{{ l.label }}</span>
          </button>
          <button class="hicon" @click="navTo('/messages')">
            <span class="hi-icon">💬</span>
            <span class="hi-label">消息<span class="notify-badge" v-if="unreadMsg > 0">{{ unreadMsg > 99 ? '99+' : unreadMsg }}</span></span>
          </button>
          <button class="hicon" @click="navTo('/notifications')">
            <span class="hi-icon">🔔</span>
            <span class="hi-label">通知<span class="notify-badge" v-if="unreadNotif > 0">{{ unreadNotif > 99 ? '99+' : unreadNotif }}</span></span>
          </button>
        </div>
      </template>
      <button v-else class="login-btn" @click="goToLogin">登录</button>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  position:fixed; top:0; left:0; right:0; height:48px; background:#fff;
  border-bottom:1px solid var(--color-border-light); display:flex; align-items:center;
  justify-content:space-between; padding:0 8px; z-index:100;
}
.header-left,.header-right{display:flex;align-items:center;min-width:80px}
.header-right{justify-content:flex-end}
.header-center{display:flex;align-items:center;justify-content:center;gap:14px;min-width:0;text-align:center}
.header-title{font-size:17px;font-weight:700;color:var(--color-primary);cursor:pointer}
.header-nav{display:flex;align-items:center;gap:2px}
.header-nav-link{font-size:var(--font-sm);line-height:1.4;color:var(--ink-500);text-decoration:none;padding:4px 8px;border-radius:6px;white-space:nowrap;transition:color .15s ease,background .15s ease}
.header-nav-link:hover{color:var(--brand-700);background:var(--brand-50)}
.header-nav-link.is-active{color:var(--brand-700);font-weight:600;background:var(--brand-50)}
@media (max-width: 768px){
  /* 不再 display:none——手机上隐藏导航等于让 /expo-intel、/expo-find 没有入口。
     改成横向滑动：窄屏挤不下 4 个链接时可滑，页面仍然可达。 */
  .header-nav{overflow-x:auto;flex-wrap:nowrap;max-width:100%;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  .header-nav::-webkit-scrollbar{display:none}
  .header-nav-link{flex-shrink:0}
}
.back-btn{background:none;border:none;font-size:18px;cursor:pointer;padding:4px 8px;color:var(--color-text)}
.login-btn{font-size:13px;border:1px solid var(--color-border);padding:4px 12px;border-radius:6px;background:none;cursor:pointer}
.header-icons{display:flex;gap:2px}
.hicon{display:flex;flex-direction:column;align-items:center;gap:1px;background:none;border:none;cursor:pointer;padding:2px 5px;border-radius:6px;min-width:40px}
.hicon:hover{background:var(--color-bg-page)}
.hi-icon{font-size:16px;line-height:1}
.hi-label{font-size:9px;color:var(--color-text-secondary);line-height:1;position:relative}
.notify-badge{position:absolute;top:-6px;right:-10px;background:#ef4444;color:#fff;font-size:8px;min-width:14px;height:14px;line-height:14px;text-align:center;border-radius:7px;padding:0 3px}
</style>
