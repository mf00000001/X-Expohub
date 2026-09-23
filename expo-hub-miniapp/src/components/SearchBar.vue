<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  placeholder?: string
  modelValue?: string
  showButton?: boolean
}>(), {
  placeholder: '搜索展会、展品、采购需求...',
  modelValue: '',
  showButton: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: [value: string]
}>()

// 本地即时保存输入值。
// 不能只依赖 props.modelValue：小程序里 v-model 回传存在时序风险，
// 一旦回传没跟上，confirm/点击时 emit 出去的就是空串，父级 if (q) 会把它整个吞掉 —— 表现为「点了没反应」。
const innerValue = ref(props.modelValue || '')

watch(() => props.modelValue, (v) => {
  const next = v ?? ''
  if (next !== innerValue.value) innerValue.value = next
})

function handleInput(e: any) {
  const v = e?.detail?.value ?? ''
  innerValue.value = v
  emit('update:modelValue', v)
}

function handleSubmit(e?: any) {
  // 取值的优先级：confirm 事件自带的值 > 本地缓存 > props
  const raw = e?.detail?.value ?? innerValue.value ?? props.modelValue ?? ''
  emit('search', String(raw).trim())
}

function handleClear() {
  innerValue.value = ''
  emit('update:modelValue', '')
  emit('search', '')
}
</script>

<template>
  <view class="search-bar" :class="{ 'has-btn': showButton }">
    <text class="search-icon" @tap="handleSubmit">🔍</text>
    <input cursor-spacing="24"
      class="search-input"
      type="text"
      :value="innerValue"
      :placeholder="placeholder"
      @input="handleInput"
      @confirm="handleSubmit"
      confirm-type="search"
    />
    <view v-if="innerValue" class="search-clear" @click="handleClear">
      <text>✕</text>
    </view>
    <view v-if="showButton" class="search-btn" @tap="handleSubmit">
      <text>搜索</text>
    </view>
  </view>
</template>

<style scoped>
.search-bar {
  position: relative;
  display: flex;
  align-items: center;
}

/* 放大镜做成实心可点区域：以前它是 position:absolute 的死区，点了什么都不发生 */
.search-icon {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  z-index: 1;
}

.search-input {
  width: 100%;
  /* 原生 input 依赖显式高度：纵向 padding 会裁掉文字（同 App.vue 的 .form-input） */
  height: 52px;
  min-height: 52px;
  padding: 0 48px 0 44px;
  border: 2px solid var(--color-border);
  border-radius: 28px;
  font-size: 15px;
  background: var(--color-white);
  line-height: 1.4;
  box-sizing: border-box;
}

/* 右侧有「搜索」按钮时，给输入文字让位 */
.search-bar.has-btn .search-input {
  padding-right: 92px;
}

.search-clear {
  position: absolute;
  right: 14px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
  border-radius: 50%;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.search-bar.has-btn .search-clear {
  right: 78px;
}

.search-btn {
  position: absolute;
  right: 6px;
  top: 6px;
  bottom: 6px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary);
  color: #fff;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
}
</style>
