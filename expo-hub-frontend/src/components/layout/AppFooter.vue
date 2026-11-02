<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

interface TabItem { path: string; label: string; icon: string; roles?: string[] }

// 每个角色只保留一套底部导航。
// 之前是「按角色过滤一份大表」，而大表里「首页/微展位/采购」在基础组和角色组里各出现一次，
// 买家会同时命中两组 → 底部出现两个「首页」。
const TAB_SETS: Record<string, TabItem[]> = {
  guest: [
    { path: '/', label: '首页', icon: '🏠' },
    { path: '/exhibitions', label: '展会', icon: '📋' },
    { path: '/micro-booths', label: '微展位', icon: '🏪' },
    { path: '/procurements', label: '采购', icon: '📦' },
  ],
  visitor: [
    { path: '/', label: '首页', icon: '🏠' },
    { path: '/exhibitions', label: '展会', icon: '📋' },
    { path: '/micro-booths', label: '微展位', icon: '🏪' },
    { path: '/procurements', label: '采购需求', icon: '📦' },
    { path: '/profile', label: '我的', icon: '👤' },
  ],
  buyer: [
    { path: '/', label: '首页', icon: '🏠' },
    { path: '/buyer/dashboard', label: '采购', icon: '📦' },
    { path: '/micro-booths', label: '微展位', icon: '🏪' },
    { path: '/favorites', label: '清单', icon: '📋' },
    { path: '/profile', label: '我的', icon: '👤' },
  ],
  exhibitor: [
    { path: '/', label: '首页', icon: '🏠' },
    { path: '/exhibitor/dashboard', label: '工作台', icon: '📊' },
    { path: '/micro-booths', label: '广场', icon: '🏪' },
    { path: '/exhibitor/products', label: '展品', icon: '📦' },
    { path: '/profile', label: '我的', icon: '👤' },
  ],
  admin: [
    { path: '/', label: '首页', icon: '🏠' },
    { path: '/admin/exhibitions', label: '展会', icon: '🎪' },
    { path: '/admin/dashboard', label: '管理', icon: '⚙️' },
    { path: '/micro-booths', label: '微展位', icon: '🏪' },
    { path: '/profile', label: '我的', icon: '👤' },
  ],
}

const tabs = computed(() => {
  const role = userStore.role || ''
  const isAuth = userStore.isLoggedIn
  const key = isAuth ? (TAB_SETS[role] ? role : 'visitor') : 'guest'
  const seen = new Set<string>()
  return TAB_SETS[key].filter((t) => {
    if (seen.has(t.path)) return false
    seen.add(t.path)
    return true
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
  <footer class="app-footer">
    <!-- 角色底部导航：原有逻辑不变，由 tabs 计算属性按登录态/角色过滤 -->
    <nav class="footer-tabs" aria-label="主导航">
      <button v-for="tab in tabs" :key="tab.path+tab.label" class="footer-tab"
              :class="{ active: activeTab === tab.path }" @click="navigateTo(tab.path)">
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.label }}</span>
      </button>
    </nav>

    <!-- 法律条款入口：PIPL 要求「醒目位置、易于访问」，所有角色（含未登录游客）都可见，
         因此不走 roles 过滤，也不依赖登录态，始终渲染 -->
    <nav class="footer-legal" aria-label="法律条款">
      <!-- 文案与 views/user/RegisterView.vue 的勾选行一致；同页跳转，不开新标签 -->
      <router-link to="/terms">《用户协议》</router-link>
      <router-link to="/privacy">《隐私政策》</router-link>
    </nav>
  </footer>
</template>

<style scoped>
/* 固定底栏：纵向两行，两行高之和 = --footer-height（总高唯一来源，定义在 src/style.css）。
   顶部分隔线画在导航行上（border-box 内在），避免 .app-footer 自身 border 再占 1px，
   导致实际高度比 --footer-height 多 1px、与内容区留白/悬浮球定位算出来的值对不上。 */
.app-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  /* 高度 = 基础 80px + iPhone 安全区（--footer-safe-area，桌面为 0）；
     全局 box-sizing:border-box，padding-bottom 已包含在 min-height 内，两处引用同一变量不会重复叠加 */
  min-height: calc(var(--footer-height) + var(--footer-safe-area));
  /* 把整条底栏内容（导航行 + 法律链接行）抬到 Home 指示条上方，背景色仍铺满安全区 */
  padding-bottom: var(--footer-safe-area);
  background: var(--bg-white);
  display: flex;
  flex-direction: column;
  z-index: 100;
}
.footer-tabs { display:flex;align-items:center;justify-content:space-around;height:var(--footer-tabs-height);border-top:1px solid var(--border-color) }
.footer-tab { flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;background:none;border:none;cursor:pointer;padding:6px 0;color:var(--text-hint);transition:color .2s }
.footer-tab.active { color:var(--primary) }
.footer-tab:hover { color:var(--primary) }
.tab-icon { font-size:20px } .tab-label { font-size:11px }

/* 法律链接行：固定高 --footer-legal-height(20px，含 1px 分隔线)，12px 小字垂直居中。
   该高度已计入 --footer-height，页面留白由 .main-content 的 padding-bottom 统一让出，
   不依赖其他区块的余量，也不再挤压上方导航项 */
.footer-legal {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  height: var(--footer-legal-height);
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  line-height: 14px;
}
.footer-legal a { color: var(--text-hint);text-decoration: none;transition: color .2s }
.footer-legal a:hover { color: var(--primary) }
.footer-legal a.router-link-active { color: var(--primary) }
</style>
