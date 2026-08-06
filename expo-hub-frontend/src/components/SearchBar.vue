<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  modelValue: string
  placeholder?: string
  showFilter?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: '搜索...',
  showFilter: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: [value: string]
  filter: []
}>()

const inputValue = ref(props.modelValue)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(inputValue, (val) => {
  emit('update:modelValue', val)
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('search', val)
  }, 400)
})

function handleClear(): void {
  inputValue.value = ''
  emit('search', '')
}
</script>

<template>
  <div class="search-bar-wrapper">
    <div class="search-bar">
      <span class="search-icon">🔍</span>
      <input
        v-model="inputValue"
        type="text"
        :placeholder="placeholder"
        class="search-input"
      />
      <button v-if="inputValue" class="clear-btn" @click="handleClear">✕</button>
    </div>
    <button v-if="showFilter" class="filter-btn" @click="$emit('filter')">
      ⚙
    </button>
  </div>
</template>

<style scoped>
.search-bar-wrapper {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.search-bar {
  flex: 1;
  display: flex;
  align-items: center;
  background: var(--bg-white);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  padding: 10px 16px;
  gap: var(--spacing-sm);
  transition: border-color 0.2s;
}
.search-bar:focus-within {
  border-color: var(--primary);
}

.search-icon {
  font-size: 16px;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  background: transparent;
  color: var(--text-primary);
}
.search-input::placeholder {
  color: var(--text-hint);
}

.clear-btn {
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
  color: var(--text-hint);
  padding: 2px 4px;
}

.filter-btn {
  background: var(--bg-white);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 18px;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.filter-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}
</style>
