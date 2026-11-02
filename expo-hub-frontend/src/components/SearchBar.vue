<script setup lang="ts">
import { ref, watch } from 'vue'

interface Props {
  modelValue: string
  placeholder?: string
  showFilter?: boolean
  /** 是否「输入即搜」：true 时保留 400ms 防抖自动触发 search（微展位广场等即时筛选场景）；
   *  false 时防抖不再触发，只在回车 / 点搜索按钮 / 失焦时触发（首页跳转型搜索用） */
  live?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: '搜索...',
  showFilter: false,
  live: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: [value: string]
  filter: []
}>()

const inputValue = ref(props.modelValue)

let debounceTimer: ReturnType<typeof setTimeout> | null = null
// 最近一次已发出的关键词：失焦时值没变就不再重复请求
let lastQuery = props.modelValue

function clearTimer(): void {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
}

// 统一的 search 出口：先取消待执行的防抖，避免同一次输入触发两次请求
function emitSearch(value: string): void {
  clearTimer()
  lastQuery = value
  emit('search', value)
}

watch(inputValue, (val) => {
  emit('update:modelValue', val)
  clearTimer()
  // live=false 时不自动搜索（首页打字停顿就会被跳走），交给回车/搜索按钮/失焦确认
  if (!props.live) return
  debounceTimer = setTimeout(() => {
    emitSearch(val)
  }, 400)
})

// 回车或点搜索按钮：立即确认
function handleSubmit(): void {
  emitSearch(inputValue.value)
}

// 失焦确认：仅非 live 模式需要（live 模式下防抖已覆盖输入变化，避免重复请求）
function handleBlur(): void {
  if (props.live) return
  if (inputValue.value === lastQuery) return
  emitSearch(inputValue.value)
}

function handleClear(): void {
  inputValue.value = ''
  emitSearch('')
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
        @keyup.enter="handleSubmit"
        @blur="handleBlur"
      />
      <button v-if="inputValue" class="clear-btn" @mousedown.prevent @click="handleClear">✕</button>
    </div>
    <!-- mousedown.prevent：避免点按钮时输入框先失焦（live=false 下会多触发一次 blur 搜索） -->
    <button type="button" class="btn btn-primary search-submit" @mousedown.prevent @click="handleSubmit">
      搜索
    </button>
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

/* 搜索按钮：沿用全局 .btn/.btn-primary 配色，仅在组件内收紧尺寸 */
.search-submit {
  flex-shrink: 0;
  padding: 10px 18px;
  white-space: nowrap;
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
