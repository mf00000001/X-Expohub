<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/composables/useI18n'

const props = defineProps<{ exhibition: Record<string, any> }>()
const { pick } = useI18n()

const id = computed(() => props.exhibition.id)
const name = computed(() => pick(props.exhibition, 'title') || props.exhibition.name || '')
const coverUrl = computed(() => props.exhibition.cover_url || props.exhibition.coverUrl || props.exhibition.cover_image || '')
const startDate = computed(() => props.exhibition.start_date || props.exhibition.startDate || '')
const endDate = computed(() => props.exhibition.end_date || props.exhibition.endDate || '')
const venue = computed(() => props.exhibition.venue || props.exhibition.location || '')
const city = computed(() => props.exhibition.city || '')
const status = computed(() => props.exhibition.status || '')
const visitorCount = computed(() => props.exhibition.visitor_count || props.exhibition.visitorCount || 0)
const exhibitorCount = computed(() => Number(props.exhibition.exhibitor_count || 0))

// 时间线标签：按日期推导（即将举办/进行中/已结束），比后台编辑状态更贴近用户视角
const timelineLabel = computed(() => {
  const st = startDate.value ? new Date(startDate.value).getTime() : NaN
  const en = endDate.value ? new Date(endDate.value).getTime() : NaN
  if (!Number.isFinite(st) || !Number.isFinite(en)) return ''
  const now = Date.now()
  if (now < st) return '即将举办'
  if (now > en) return '已结束'
  return '进行中'
})

const statusLabelMap: Record<string, string> = {
  draft: '草稿', pending: '待审核', published: '已发布',
  ongoing: '进行中', finished: '已结束', cancelled: '已取消',
}

function formatDate(d: string): string {
  if (!d) return ''
  try { const dt = new Date(d); return dt.toLocaleDateString('zh-CN') } catch { return d }
}

function formatNumber(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

const tagClass = computed(() => {
  if (timelineLabel.value === '进行中') return 'tag-success'
  if (timelineLabel.value === '即将举办') return 'tag-warning'
  if (timelineLabel.value === '已结束') return 'tag-info'
  if (status.value === 'published' || status.value === 'ongoing') return 'tag-success'
  if (status.value === 'pending') return 'tag-warning'
  return 'tag-info'
})
import ExpoCover from '@/components/ExpoCover.vue'
</script>

<template>
  <div class="expo-card card" @click="$emit('click', id)">
    <div class="expo-cover">
      <!-- 无封面图时由 ExpoCover 渲染深蓝渐变兜底，不再依赖可能不存在的占位图 -->
      <ExpoCover class="card-cover" :src="coverUrl" :title="name" ratio="16/9" />
      <span class="expo-status tag" :class="tagClass">
        {{ timelineLabel || statusLabelMap[status] || status }}
      </span>
    </div>
    <div class="expo-body">
      <h3 class="expo-name">{{ name }}</h3>
      <div class="expo-meta">
        <span class="meta-item">📅 {{ formatDate(startDate) }} ~ {{ formatDate(endDate) }}</span>
        <span class="meta-item">📍{{ city }}{{ city && venue ? ' / ' : '' }}{{ venue }}</span>
      </div>
      <div class="expo-footer">
        <span class="visitor-count">👁 {{ formatNumber(visitorCount) }} 浏览</span>
        <span v-if="exhibitorCount" class="exhibitor-count">🧑‍💼 {{ exhibitorCount }} 家展商</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.expo-card {
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  padding: 0;
}
.expo-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.expo-cover {
  position: relative;
  width: 100%;
  height: 160px;
  overflow: hidden;
  background: var(--bg-color);
}
:deep(.card-cover) {
  width: 100%;
  height: 100%;
}
:deep(.card-cover .cover-img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.expo-status {
  position: absolute;
  top: 8px;
  right: 8px;
}

.expo-body {
  padding: var(--spacing-md);
}

.expo-name {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: var(--spacing-sm);
  color: var(--text-primary);
  line-height: 1.4;
}

.expo-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: var(--spacing-sm);
}

.meta-item {
  font-size: 13px;
  color: var(--text-secondary);
}

.expo-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.visitor-count {
  font-size: 12px;
  color: var(--text-hint);
}
.exhibitor-count {
  margin-left: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
