<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
import FloatingPoints from '@/components/FloatingPoints.vue'

const route = useRoute()
const userStore = useUserStore()

// 冷启动时用 token 刷新一次资料：
// 只依赖 localStorage 里持久化的 profile 会出现「角色过期/串号」——
// 例如服务端把角色升级为 admin、或同一浏览器换了 token，
// 页面仍按旧角色渲染，守卫也会据此跳到错误的首页。
onMounted(() => {
  if (localStorage.getItem('access_token')) {
    userStore.fetchProfile().catch(() => { /* 401 时由 axios 拦截器处理登出 */ })
  }
})

/**
 * 底部导航只对非角色专属页面显示
 * 角色专属页面：/visitor, /exhibitor, /procurement, /admin 及其子路由
 */
const showFooter = computed(() => {
  // router meta 中设置了 showFooter
  if (route.meta.showFooter === false) return false
  return true
})
</script>

<template>
  <AppHeader />
  <main class="main-content">
    <router-view />
  </main>
  <AppFooter v-if="showFooter" />
  <FloatingPoints />
</template>


<style scoped>
.main-content {
  flex: 1;
  padding-top: var(--header-height);
  /* 底部留白 = 页脚总高 + 16px 间距（--spacing-md），与 style.css 中同名规则保持一致 */
  padding-bottom: calc(var(--footer-height) + var(--spacing-md) + var(--footer-safe-area));
  min-height: 100vh;
}
</style>
