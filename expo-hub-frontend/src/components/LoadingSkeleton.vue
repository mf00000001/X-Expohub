<script setup lang="ts">
interface Props {
  type?: 'card' | 'list' | 'detail'
  count?: number
}

withDefaults(defineProps<Props>(), {
  type: 'card',
  count: 3,
})
</script>

<template>
  <div class="skeleton-container">
    <!-- 卡片骨架 -->
    <template v-if="type === 'card'">
      <div v-for="i in count" :key="i" class="skeleton-card">
        <div class="skeleton-box skeleton-image"></div>
        <div class="skeleton-card-body">
          <div class="skeleton-box skeleton-title"></div>
          <div class="skeleton-box skeleton-text"></div>
          <div class="skeleton-box skeleton-text short"></div>
        </div>
      </div>
    </template>

    <!-- 列表骨架 -->
    <template v-if="type === 'list'">
      <div v-for="i in count" :key="i" class="skeleton-list-item">
        <div class="skeleton-box skeleton-avatar"></div>
        <div class="skeleton-list-body">
          <div class="skeleton-box skeleton-title"></div>
          <div class="skeleton-box skeleton-text"></div>
        </div>
        <div class="skeleton-box skeleton-badge"></div>
      </div>
    </template>

    <!-- 详情骨架 -->
    <template v-if="type === 'detail'">
      <div class="skeleton-detail">
        <div class="skeleton-box skeleton-hero"></div>
        <div class="skeleton-box skeleton-title large"></div>
        <div class="skeleton-box skeleton-text"></div>
        <div class="skeleton-box skeleton-text"></div>
        <div class="skeleton-box skeleton-text short"></div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.skeleton-box {
  background: linear-gradient(90deg, #e5e7eb 25%, #f3f4f6 50%, #e5e7eb 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Card */
.skeleton-card {
  background: var(--bg-white);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.skeleton-image {
  height: 160px;
  border-radius: 0;
}

.skeleton-card-body {
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* List */
.skeleton-list-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  background: var(--bg-white);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
}

.skeleton-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.skeleton-list-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.skeleton-badge {
  width: 50px;
  height: 22px;
  border-radius: var(--radius-full);
}

/* Detail */
.skeleton-detail {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.skeleton-hero {
  height: 220px;
  width: 100%;
}

/* Lines */
.skeleton-title {
  height: 18px;
  width: 60%;
}

.skeleton-title.large {
  height: 24px;
  width: 80%;
}

.skeleton-text {
  height: 14px;
  width: 100%;
}

.skeleton-text.short {
  width: 40%;
}
</style>
