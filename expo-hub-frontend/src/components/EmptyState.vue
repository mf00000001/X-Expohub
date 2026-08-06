<script setup lang="ts">
interface Props {
  icon?: string
  text?: string
  showAction?: boolean
  actionText?: string
}

withDefaults(defineProps<Props>(), {
  icon: '📭',
  text: '暂无数据',
  showAction: false,
  actionText: '去添加',
})

const emit = defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="empty-state">
    <span class="empty-icon">{{ icon }}</span>
    <p class="empty-text">{{ text }}</p>
    <button v-if="showAction" class="btn btn-primary btn-sm" @click="$emit('action')">
      {{ actionText }}
    </button>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl) var(--spacing-md);
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-md);
}

.empty-text {
  font-size: 15px;
  color: var(--text-hint);
  margin-bottom: var(--spacing-md);
}
</style>
