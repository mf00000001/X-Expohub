<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCitiesStore } from '@/stores/cities'
import Loading from '@/components/common/Loading.vue'

const route = useRoute()
const router = useRouter()
const citiesStore = useCitiesStore()
const query = ref((route.query.q as string) || '')

onMounted(() => {
  if (query.value) {
    citiesStore.search(query.value)
  }
  citiesStore.fetchHotCities()
})

watch(query, (val) => {
  if (val.trim()) {
    citiesStore.search(val)
  } else {
    citiesStore.clearSearch()
  }
})

function selectCity(city: { id: number }) {
  router.push({ name: 'city-detail', params: { id: city.id } })
}
</script>

<template>
  <div class="space-y-5 animate-fade-in">
    <button @click="router.back()" class="btn-secondary text-sm !px-3 !py-1.5">
      ← 返回
    </button>

    <h1 class="text-xl font-bold text-gray-800">🔍 搜索城市</h1>

    <!-- 搜索框 -->
    <div class="relative">
      <input
        v-model="query"
        type="text"
        placeholder="输入城市名称..."
        class="input-field pl-10 text-base"
        autofocus
      />
      <svg
        class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400"
        fill="none" stroke="currentColor" viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    </div>

    <!-- 搜索结果 -->
    <div v-if="citiesStore.searching" class="card">
      <Loading :rows="4" type="list" />
    </div>

    <div v-else-if="citiesStore.searchError" class="card text-center text-red-500 py-8">
      {{ citiesStore.searchError }}
    </div>

    <div v-else-if="citiesStore.hasResults" class="card">
      <div class="space-y-1">
        <div
          v-for="city in citiesStore.searchResults"
          :key="city.id"
          @click="selectCity(city)"
          class="flex items-center justify-between p-3 rounded-xl hover:bg-blue-50 cursor-pointer transition-colors"
        >
          <div>
            <p class="font-medium text-gray-800">{{ city.name }}</p>
            <p class="text-xs text-gray-400">
              {{ city.state ? city.state + ', ' : '' }}{{ city.country }}
            </p>
          </div>
          <span class="text-gray-300 text-lg">›</span>
        </div>
      </div>
    </div>

    <!-- 无结果 -->
    <div v-else-if="query && !citiesStore.searching" class="card text-center py-8 text-gray-400">
      未找到相关城市
    </div>

    <!-- 热门城市 -->
    <div class="card">
      <h3 class="text-base font-semibold text-gray-700 mb-3">🔥 热门城市</h3>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <button
          v-for="city in citiesStore.hotCities"
          :key="city.id"
          @click="selectCity(city)"
          class="p-3 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50 text-sm font-medium text-gray-700 transition-all"
        >
          {{ city.name }}
        </button>
        <!-- 预设热门城市（API 无数据时的降级） -->
        <template v-if="!citiesStore.hotCities.length">
          <button
            v-for="c in ['北京', '上海', '广州', '深圳', '杭州', '成都', '西安', '重庆']"
            :key="c"
            @click="query = c; citiesStore.search(c)"
            class="p-3 rounded-xl border border-gray-200 hover:border-blue-300 hover:bg-blue-50 text-sm font-medium text-gray-700 transition-all"
          >
            {{ c }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>
