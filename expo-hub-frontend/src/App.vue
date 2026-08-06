<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppFooter from '@/components/layout/AppFooter.vue'

const route = useRoute()

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
</template>

<style scoped>
.main-content {
  flex: 1;
  padding-top: var(--header-height);
  padding-bottom: calc(var(--footer-height) + var(--spacing-lg));
  min-height: 100vh;
}
</style>
