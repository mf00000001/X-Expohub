<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useFavorites } from '@/composables/useFavorites'
import Loading from '@/components/common/Loading.vue'
import ErrorRetry from '@/components/common/ErrorRetry.vue'

const router = useRouter()
const { favorites, loading, error, fetchFavorites, remove, reorder } = useFavorites()
const removingId = ref<number | null>(null)

onMounted(() => {
  fetchFavorites()
})

async function handleRemove(favId: number) {
  removingId.value = favId
  try {
    await remove(favId)
  } catch {
    // error handled in composable
  } finally {
    removingId.value = null
  }
}

function goToCity(cityId: number) {
  router.push({ name: 'city-detail', params: { id: cityId } })
}

// 简单的上移/下移
function moveUp(index: number) {
  if (index === 0) return
  const ids = favorites.value.map((f) => f.id)
  ;[ids[index], ids[index - 1]] = [ids[index - 1], ids[index]]
  reorder(ids)
}

function moveDown(index: number) {
  if (index === favorites.value.length - 1) return
  const ids = favorites.value.map((f) => f.id)
  ;[ids[index], ids[index + 1]] = [ids[index + 1], ids[index]]
  reorder(ids)
}
</script>

<template>
  <div class="space-y-5 animate-fade-in">
    <button @click="router.back()" class="btn-secondary text-sm !px-3 !py-1.5">
      ← 返回
    </button>

    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-gray-800">⭐ 我的收藏</h1>
      <span class="text-sm text-gray-500">{{ favorites.length }} 个城市</span>
    </div>

    <Loading v-if="loading" :rows="4" type="list" />
    <ErrorRetry
      v-else-if="error"
      :message="error"
      @retry="fetchFavorites"
    />

    <!-- 收藏列表 -->
    <div v-else-if="favorites.length > 0" class="card !p-0 divide-y divide-gray-100">
      <div
        v-for="(fav, index) in favorites"
        :key="fav.id"
        class="flex items-center gap-3 p-4 hover:bg-gray-50 transition-colors"
      >
        <!-- 排序按钮 -->
        <div class="flex flex-col gap-0.5">
          <button
            @click="moveUp(index)"
            :disabled="index === 0"
            class="text-gray-400 hover:text-gray-600 disabled:opacity-30 text-xs leading-none"
          >
            ▲
          </button>
          <button
            @click="moveDown(index)"
            :disabled="index === favorites.length - 1"
            class="text-gray-400 hover:text-gray-600 disabled:opacity-30 text-xs leading-none"
          >
            ▼
          </button>
        </div>

        <!-- 城市信息 -->
        <div
          @click="goToCity(fav.city_id)"
          class="flex-1 cursor-pointer"
        >
          <p class="font-medium text-gray-800">{{ fav.city?.name || `城市 #${fav.city_id}` }}</p>
          <p v-if="fav.city" class="text-xs text-gray-400">
            {{ fav.city.country }}
          </p>
        </div>

        <!-- 删除按钮 -->
        <button
          @click="handleRemove(fav.id)"
          :disabled="removingId === fav.id"
          class="text-red-400 hover:text-red-600 disabled:opacity-50 p-1 transition-colors"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 空收藏 -->
    <div v-else class="card text-center py-12">
      <div class="text-5xl mb-4">⭐</div>
      <h3 class="text-lg font-semibold text-gray-700 mb-2">还没有收藏</h3>
      <p class="text-sm text-gray-500 mb-4">
        去搜索城市并添加收藏吧
      </p>
      <RouterLink to="/search" class="btn-primary">
        🔍 搜索城市
      </RouterLink>
    </div>
  </div>
</template>
