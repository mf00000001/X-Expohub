<script setup lang="ts">
import type { Exhibition } from '@/api/exhibition'

defineProps<{
  exhibition: Exhibition
}>()

defineEmits<{
  click: []
}>()

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    published: '进行中',
    ongoing: '进行中',
    draft: '即将开始',
    pending: '审核中',
    ended: '已结束',
    cancelled: '已取消',
  }
  return map[status] || status
}

function statusClass(status: string): string {
  if (status === 'published' || status === 'ongoing') return 'tag-green'
  if (status === 'draft' || status === 'pending') return 'tag-blue'
  if (status === 'ended') return 'tag-gray'
  if (status === 'cancelled') return 'tag-red'
  return 'tag-gray'
}
</script>

<template>
  <div class="expo-card card" @click="$emit('click')">
    <!-- 封面 -->
    <div class="expo-cover" v-if="exhibition.cover_image">
      <img :src="exhibition.cover_image" :alt="exhibition.title" />
    </div>
    <div class="expo-cover-placeholder" v-else>
      <span class="placeholder-icon">🎪</span>
    </div>

    <div class="card-body">
      <!-- 标题 + 状态 -->
      <div class="expo-header">
        <h3 class="expo-title" :title="exhibition.title">{{ exhibition.title }}</h3>
        <span class="tag" :class="statusClass(exhibition.status)">
          {{ statusLabel(exhibition.status) }}
        </span>
      </div>

      <!-- 描述 -->
      <p class="expo-desc text-secondary text-sm" v-if="exhibition.description">
        {{ exhibition.description.slice(0, 80) }}{{ exhibition.description.length > 80 ? '...' : '' }}
      </p>

      <!-- 元信息：时间、地点、主办方 -->
      <div class="expo-meta">
        <div class="meta-item">
          <span class="meta-icon">📅</span>
          <span class="meta-text">{{ exhibition.start_date }} ~ {{ exhibition.end_date }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-icon">📍</span>
          <span class="meta-text">{{ exhibition.location }}</span>
        </div>
        <div class="meta-item" v-if="exhibition.organizer_name">
          <span class="meta-icon">👤</span>
          <span class="meta-text">{{ exhibition.organizer_name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.expo-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
}
.expo-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}

/* 封面 */
.expo-cover {
  height: 180px;
  overflow: hidden;
  flex-shrink: 0;
}
.expo-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}
.expo-card:hover .expo-cover img {
  transform: scale(1.05);
}

.expo-cover-placeholder {
  height: 180px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.placeholder-icon {
  font-size: 48px;
  opacity: 0.7;
}

/* 标题区域 */
.expo-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.expo-title {
  font-size: 17px;
  font-weight: 600;
  line-height: 1.3;
  flex: 1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 描述 */
.expo-desc {
  line-height: 1.5;
  margin-bottom: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 元信息 */
.expo-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--color-border);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-icon {
  font-size: 14px;
  flex-shrink: 0;
  width: 18px;
  text-align: center;
}

.meta-text {
  font-size: 13px;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
