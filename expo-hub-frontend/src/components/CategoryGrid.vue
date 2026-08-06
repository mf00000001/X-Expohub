<script setup lang="ts">
defineProps<{ active?: string[] }>()
const emit = defineEmits<{ (e: 'select', cat: string): void }>()

const categories = [
  { name: '电子及家电', icon: '📱', group: '电子电器' },
  { name: '照明', icon: '💡', group: '电子电器' },
  { name: '车辆及配件', icon: '🚗', group: '机械装备' },
  { name: '五金工具', icon: '🔧', group: '机械装备' },
  { name: '机械', icon: '⚙️', group: '机械装备' },
  { name: '建材', icon: '🧱', group: '建筑装饰' },
  { name: '化工产品', icon: '🧪', group: '工业原料' },
  { name: '能源', icon: '⚡', group: '工业原料' },
  { name: '日用消费品', icon: '🛍️', group: '消费品' },
  { name: '礼品', icon: '🎁', group: '消费品' },
  { name: '纺织服装', icon: '👕', group: '纺织鞋服' },
  { name: '鞋类', icon: '👟', group: '纺织鞋服' },
  { name: '家居装饰品', icon: '🛋️', group: '建筑装饰' },
  { name: '办公箱包及休闲用品', icon: '💼', group: '消费品' },
  { name: '食品', icon: '🍜', group: '食品医药' },
  { name: '医药及医疗保健', icon: '💊', group: '食品医药' },
  { name: 'AI/科技', icon: '🤖', group: '新兴技术' },
  { name: '综合服务', icon: '🏢', group: '新兴技术' },
]
</script>

<template>
  <div class="cat-grid">
    <button v-for="cat in categories" :key="cat.name"
            :class="['cat-btn', { active: active?.includes(cat.name) }]"
            @click="emit('select', cat.name)">
      <span class="cat-icon">{{ cat.icon }}</span>
      <span class="cat-name">{{ cat.name }}</span>
    </button>
  </div>
</template>

<style scoped>
.cat-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px;
}
.cat-btn {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 16px 10px; border: 2px solid var(--color-border-light);
  border-radius: 12px; background: var(--color-bg-card); cursor: pointer;
  transition: all 0.2s;
}
.cat-btn:hover { border-color: var(--color-primary); transform: translateY(-2px); box-shadow: var(--shadow); }
.cat-btn.active { border-color: var(--color-primary); background: var(--color-primary-light); }
.cat-icon { font-size: 28px; }
.cat-name { font-size: 13px; font-weight: 500; color: var(--color-text); text-align: center; line-height: 1.3; }
</style>
