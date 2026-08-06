<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

// Simulated activity feed — in production, this would come from WebSocket or polling
const activities = ref([
  { text: '深圳XX科技公司 报名了广交会', time: '3分钟前', icon: '📋' },
  { text: '上海YY贸易 发布了采购需求（电子元器件）', time: '8分钟前', icon: '📦' },
  { text: '广州ZZ制造 升级为旗舰会员', time: '12分钟前', icon: '⭐' },
  { text: '北京AA集团 预约了上海进博会', time: '15分钟前', icon: '🎫' },
  { text: '杭州BB科技 被12人收藏', time: '20分钟前', icon: '❤️' },
])

let timer: number | null = null
onMounted(() => {
  timer = window.setInterval(() => {
    // Rotate one activity to bottom to simulate live feed
    const first = activities.value.shift()
    if (first) activities.value.push(first)
  }, 5000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="feed">
    <div class="feed-header">
      <span class="feed-dot"></span>
      <span>实时动态</span>
    </div>
    <div class="feed-list">
      <div class="feed-item" v-for="(a, i) in activities" :key="i">
        <span class="feed-icon">{{ a.icon }}</span>
        <span class="feed-text">{{ a.text }}</span>
        <span class="feed-time">{{ a.time }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.feed {
  background: var(--color-bg-card); border-radius: 12px; padding: 16px;
  box-shadow: var(--shadow-sm); overflow: hidden;
}
.feed-header { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; margin-bottom: 12px; }
.feed-dot { width: 8px; height: 8px; border-radius: 50%; background: #10b981; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
.feed-list { display: flex; flex-direction: column; gap: 8px; }
.feed-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--color-text-regular); padding: 6px 0; border-bottom: 1px solid var(--color-border-lighter); animation: fadeIn 0.5s; }
.feed-item:last-child { border-bottom: none; }
.feed-icon { font-size: 14px; flex-shrink: 0; }
.feed-text { flex: 1; }
.feed-time { font-size: 11px; color: var(--color-text-placeholder); flex-shrink: 0; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
</style>
