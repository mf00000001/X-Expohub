<script setup lang="ts">
import { computed } from 'vue'
import type { Exhibition } from '@/api/exhibition'
import { isHttpUrl } from '@/utils/image'

const props = defineProps<{
  exhibition: Exhibition
}>()

defineEmits<{
  click: []
}>()

// 封面可能是脏数据（非 http 链接），校验不过就走占位符，避免破图
const hasCover = computed(() => isHttpUrl(props.exhibition.cover_image))

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
  <view class="expo-card card" @click="$emit('click')">
    <image
      v-if="hasCover"
      class="expo-cover"
      :src="exhibition.cover_image"
      mode="aspectFill"
    />
    <view v-else class="expo-cover expo-cover-placeholder">
      <text class="placeholder-icon">🎪</text>
    </view>

    <view class="card-body">
      <view class="expo-header">
        <text class="expo-title">{{ exhibition.title }}</text>
        <text class="tag" :class="statusClass(exhibition.status)">
          {{ statusLabel(exhibition.status) }}
        </text>
      </view>

      <text v-if="exhibition.description" class="expo-desc text-secondary text-sm">
        {{ exhibition.description.slice(0, 80) }}{{ exhibition.description.length > 80 ? '...' : '' }}
      </text>

      <view class="expo-meta">
        <view class="meta-item">
          <text class="meta-icon">📅</text>
          <text class="meta-text">{{ exhibition.start_date }} ~ {{ exhibition.end_date }}</text>
        </view>
        <view class="meta-item">
          <text class="meta-icon">📍</text>
          <text class="meta-text">{{ exhibition.location }}</text>
        </view>
        <view v-if="exhibition.organizer_name" class="meta-item">
          <text class="meta-icon">👤</text>
          <text class="meta-text">{{ exhibition.organizer_name }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.expo-card {
  display: flex;
  flex-direction: column;
}

.expo-cover {
  width: 100%;
  height: 360rpx;
  flex-shrink: 0;
  display: block;
  background-color: #f3f4f6;
}

.expo-cover-placeholder {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-icon {
  font-size: 48px;
  opacity: 0.7;
}

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
}

.expo-desc {
  line-height: 1.5;
  margin-bottom: 14px;
  display: block;
}

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
  flex: 1;
}
</style>
