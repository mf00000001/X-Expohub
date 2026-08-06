<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

interface Props {
  /** 允许访问的角色列表 */
  roles: string[]
  /** 角色不匹配时是否显示替代内容 */
  fallback?: string
}

const props = withDefaults(defineProps<Props>(), {
  fallback: 'hidden',
})

const userStore = useUserStore()

const hasAccess = computed(() => {
  if (!userStore.role) return false
  return props.roles.includes(userStore.role)
})
</script>

<template>
  <template v-if="hasAccess">
    <slot></slot>
  </template>
  <template v-else-if="fallback === 'hidden'">
    <!-- 完全隐藏 -->
  </template>
  <template v-else>
    <div class="role-guard-fallback">
      {{ fallback }}
    </div>
  </template>
</template>

<style scoped>
.role-guard-fallback {
  padding: var(--spacing-lg);
  text-align: center;
  color: var(--text-hint);
  font-size: 14px;
}
</style>
