<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useSettingsStore } from '@/stores/settings'
import type { TemperatureUnit, Language } from '@/stores/settings'

const router = useRouter()
const settings = useSettingsStore()

function handleUnitChange(e: Event) {
  const target = e.target as HTMLSelectElement
  settings.setUnit(target.value as TemperatureUnit)
}

function handleLangChange(e: Event) {
  const target = e.target as HTMLSelectElement
  settings.setLanguage(target.value as Language)
}
</script>

<template>
  <div class="space-y-5 animate-fade-in max-w-lg mx-auto">
    <button @click="router.back()" class="btn-secondary text-sm !px-3 !py-1.5">
      ← 返回
    </button>

    <h1 class="text-xl font-bold text-gray-800">⚙️ 设置</h1>

    <!-- 温度单位 -->
    <div class="card">
      <h3 class="text-base font-semibold text-gray-700 mb-4">🌡️ 温度单位</h3>
      <div class="flex gap-3">
        <label class="flex-1 cursor-pointer">
          <input
            type="radio"
            value="celsius"
            :checked="settings.temperatureUnit === 'celsius'"
            @change="settings.setUnit('celsius')"
            class="sr-only"
          />
          <span
            class="block text-center p-3 rounded-xl border-2 transition-all"
            :class="
              settings.temperatureUnit === 'celsius'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            "
          >
            <span class="text-lg font-bold">℃</span>
            <span class="block text-xs mt-1">摄氏度</span>
          </span>
        </label>
        <label class="flex-1 cursor-pointer">
          <input
            type="radio"
            value="fahrenheit"
            :checked="settings.temperatureUnit === 'fahrenheit'"
            @change="settings.setUnit('fahrenheit')"
            class="sr-only"
          />
          <span
            class="block text-center p-3 rounded-xl border-2 transition-all"
            :class="
              settings.temperatureUnit === 'fahrenheit'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            "
          >
            <span class="text-lg font-bold">℉</span>
            <span class="block text-xs mt-1">华氏度</span>
          </span>
        </label>
      </div>
    </div>

    <!-- 语言 -->
    <div class="card">
      <h3 class="text-base font-semibold text-gray-700 mb-4">🌐 语言</h3>
      <div class="flex gap-3">
        <label class="flex-1 cursor-pointer">
          <input
            type="radio"
            value="zh"
            :checked="settings.language === 'zh'"
            @change="settings.setLanguage('zh')"
            class="sr-only"
          />
          <span
            class="block text-center p-3 rounded-xl border-2 transition-all"
            :class="
              settings.language === 'zh'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            "
          >
            中文
          </span>
        </label>
        <label class="flex-1 cursor-pointer">
          <input
            type="radio"
            value="en"
            :checked="settings.language === 'en'"
            @change="settings.setLanguage('en')"
            class="sr-only"
          />
          <span
            class="block text-center p-3 rounded-xl border-2 transition-all"
            :class="
              settings.language === 'en'
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            "
          >
            English
          </span>
        </label>
      </div>
    </div>

    <!-- 关于 -->
    <div class="card">
      <h3 class="text-base font-semibold text-gray-700 mb-3">ℹ️ 关于</h3>
      <div class="space-y-2 text-sm text-gray-600">
        <p>天气查询平台 v1.0.0</p>
        <p>技术栈：Vue 3 + TypeScript + Tailwind CSS + Pinia</p>
        <p>数据来源：开放气象 API</p>
        <p class="text-xs text-gray-400 mt-3">
          天气数据仅供参考，不构成出行决策依据
        </p>
      </div>
    </div>
  </div>
</template>
