<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const mapLoaded = ref(false)
const mapError = ref(false)

// 天气地图 - placeholder 实现
// 实际项目中可以集成 Leaflet / OpenLayers / 高德地图等
const layers = [
  { id: 'temp', name: '温度', icon: '🌡️' },
  { id: 'precip', name: '降水', icon: '🌧️' },
  { id: 'wind', name: '风场', icon: '🌬️' },
  { id: 'cloud', name: '云量', icon: '☁️' },
  { id: 'pressure', name: '气压', icon: '📊' },
]
const activeLayer = ref('temp')
</script>

<template>
  <div class="space-y-5 animate-fade-in">
    <button @click="router.back()" class="btn-secondary text-sm !px-3 !py-1.5">
      ← 返回
    </button>

    <h1 class="text-xl font-bold text-gray-800">🗺️ 天气地图</h1>

    <!-- 图层切换 -->
    <div class="flex gap-2 overflow-x-auto pb-1">
      <button
        v-for="layer in layers"
        :key="layer.id"
        @click="activeLayer = layer.id"
        class="shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-all"
        :class="
          activeLayer === layer.id
            ? 'bg-blue-500 text-white shadow-md'
            : 'bg-white border border-gray-200 text-gray-600 hover:border-blue-300'
        "
      >
        {{ layer.icon }} {{ layer.name }}
      </button>
    </div>

    <!-- 地图区域 placeholder -->
    <div
      class="card !p-0 overflow-hidden"
      style="min-height: 60vh"
    >
      <div
        class="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50"
        style="min-height: 60vh"
      >
        <div class="text-center p-8">
          <div class="text-7xl mb-4">🗺️</div>
          <h3 class="text-lg font-semibold text-gray-700 mb-2">天气地图</h3>
          <p class="text-sm text-gray-500 mb-4 max-w-md">
            当前显示：<strong>{{ layers.find((l) => l.id === activeLayer)?.name }}</strong> 图层
          </p>
          <p class="text-xs text-gray-400">
            地图组件需要接入第三方地图服务（如 Leaflet / 高德地图 / Mapbox）
            <br />
            此处为 placeholder，可在后续迭代中替换为真实地图
          </p>
          <div class="mt-6 grid grid-cols-2 gap-3 max-w-xs mx-auto">
            <div class="p-3 bg-blue-100 rounded-xl">
              <p class="text-xs text-blue-600">📍 北京</p>
              <p class="text-lg font-bold text-blue-800">22°</p>
            </div>
            <div class="p-3 bg-red-100 rounded-xl">
              <p class="text-xs text-red-600">📍 上海</p>
              <p class="text-lg font-bold text-red-800">28°</p>
            </div>
            <div class="p-3 bg-yellow-100 rounded-xl">
              <p class="text-xs text-yellow-700">📍 广州</p>
              <p class="text-lg font-bold text-yellow-800">30°</p>
            </div>
            <div class="p-3 bg-green-100 rounded-xl">
              <p class="text-xs text-green-700">📍 成都</p>
              <p class="text-lg font-bold text-green-800">25°</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
