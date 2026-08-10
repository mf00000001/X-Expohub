<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useSettingsStore } from '@/stores/settings'

const router = useRouter()
const userStore = useUserStore()
const settingsStore = useSettingsStore()
const searchQuery = ref('')
const mobileMenuOpen = ref(false)

function handleSearch() {
  const q = searchQuery.value.trim()
  if (q) {
    router.push({ name: 'search', query: { q } })
    searchQuery.value = ''
    mobileMenuOpen.value = false
  }
}

function handleLogout() {
  userStore.logout()
  router.push({ name: 'home' })
}
</script>

<template>
  <header class="sticky top-0 z-50 glass border-b border-gray-200/60 shadow-sm">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-14 sm:h-16">
        <!-- Logo -->
        <RouterLink
          to="/"
          class="flex items-center gap-2 text-lg sm:text-xl font-bold text-blue-600 hover:text-blue-700 transition-colors shrink-0"
        >
          <span class="text-2xl">🌤️</span>
          <span class="hidden sm:inline">天气查询</span>
        </RouterLink>

        <!-- 搜索框 (桌面端) -->
        <form
          @submit.prevent="handleSearch"
          class="hidden md:flex flex-1 max-w-md mx-4"
        >
          <div class="relative w-full">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索城市..."
              class="input-field pl-10 pr-4 py-2 text-sm"
            />
            <svg
              class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
        </form>

        <!-- 导航按钮 (桌面端) -->
        <nav class="hidden md:flex items-center gap-1">
          <RouterLink to="/map" class="btn-secondary text-sm !px-3 !py-1.5">
            🗺️ 地图
          </RouterLink>
          <RouterLink
            v-if="userStore.isLoggedIn"
            to="/favorites"
            class="btn-secondary text-sm !px-3 !py-1.5"
          >
            ⭐ 收藏
          </RouterLink>
          <RouterLink to="/settings" class="btn-secondary text-sm !px-3 !py-1.5">
            ⚙️
          </RouterLink>

          <template v-if="userStore.isLoggedIn">
            <span class="text-sm text-gray-600 ml-1">
              {{ userStore.user?.username }}
            </span>
            <button
              @click="handleLogout"
              class="btn-secondary text-sm !px-3 !py-1.5"
            >
              退出
            </button>
          </template>
          <template v-else>
            <RouterLink to="/login" class="btn-outline text-sm !px-3 !py-1.5">
              登录
            </RouterLink>
            <RouterLink to="/register" class="btn-primary text-sm !px-3 !py-1.5">
              注册
            </RouterLink>
          </template>
        </nav>

        <!-- 移动端菜单按钮 -->
        <button
          @click="mobileMenuOpen = !mobileMenuOpen"
          class="md:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              v-if="!mobileMenuOpen"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 6h16M4 12h16M4 18h16"
            />
            <path
              v-else
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      <!-- 移动端展开菜单 -->
      <Transition name="slide">
        <div v-if="mobileMenuOpen" class="md:hidden pb-4 space-y-3">
          <form @submit.prevent="handleSearch">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索城市..."
              class="input-field text-sm"
            />
          </form>
          <div class="flex flex-col gap-2">
            <RouterLink
              to="/map"
              @click="mobileMenuOpen = false"
              class="btn-secondary text-sm justify-center"
            >
              🗺️ 天气地图
            </RouterLink>
            <RouterLink
              v-if="userStore.isLoggedIn"
              to="/favorites"
              @click="mobileMenuOpen = false"
              class="btn-secondary text-sm justify-center"
            >
              ⭐ 我的收藏
            </RouterLink>
            <RouterLink
              to="/settings"
              @click="mobileMenuOpen = false"
              class="btn-secondary text-sm justify-center"
            >
              ⚙️ 设置
            </RouterLink>
            <template v-if="userStore.isLoggedIn">
              <button
                @click="handleLogout"
                class="btn-secondary text-sm justify-center"
              >
                退出登录
              </button>
            </template>
            <template v-else>
              <RouterLink
                to="/login"
                @click="mobileMenuOpen = false"
                class="btn-outline text-sm justify-center"
              >
                登录
              </RouterLink>
              <RouterLink
                to="/register"
                @click="mobileMenuOpen = false"
                class="btn-primary text-sm justify-center"
              >
                注册
              </RouterLink>
            </template>
          </div>
        </div>
      </Transition>
    </div>
  </header>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
