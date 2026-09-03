<script setup lang="ts">
defineProps<{
  placeholder?: string
}>()

const modelValue = defineModel<string>({ default: '' })
const emit = defineEmits<{
  search: [value: string]
}>()

function handleSubmit() {
  emit('search', modelValue.value.trim())
}

function handleClear() {
  modelValue.value = ''
  emit('search', '')
}
</script>

<template>
  <div class="search-bar">
    <span class="search-icon">🔍</span>
    <input
      v-model="modelValue"
      type="text"
      class="search-input"
      :placeholder="placeholder || '搜索展会、展品、采购需求...'"
      @keyup.enter="handleSubmit"
    />
    <button v-if="modelValue" class="search-clear" @click="handleClear" type="button">✕</button>
  </div>
</template>

<style scoped>
.search-bar {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 16px;
  font-size: 16px;
  pointer-events: none;
  z-index: 1;
}

.search-input {
  width: 100%;
  padding: 14px 48px 14px 44px;
  border: 2px solid var(--color-border);
  border-radius: 28px;
  font-size: 15px;
  background: var(--color-white);
  transition: border-color 0.2s, box-shadow 0.2s;
  line-height: 1.4;
}

.search-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
}

.search-clear {
  position: absolute;
  right: 14px;
  background: none;
  border: none;
  color: var(--color-text-secondary);
  font-size: 16px;
  padding: 4px;
  cursor: pointer;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.search-clear:hover {
  background: var(--color-border);
  color: var(--color-text);
}
</style>
