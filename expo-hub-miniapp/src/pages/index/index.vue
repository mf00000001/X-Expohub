<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import ExpoCard from '@/components/ExpoCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'

const exhibitions = ref<Exhibition[]>([])
const loading = ref(true)
const searchKeyword = ref('')
const activeCity = ref('')

// 热门城市标签
const hotCities = [
  { name: '上海', icon: '🏙️' },
  { name: '北京', icon: '🏛️' },
  { name: '深圳', icon: '🌆' },
  { name: '广州', icon: '🏢' },
  { name: '成都', icon: '🐼' },
  { name: '杭州', icon: '🪷' },
  { name: '南京', icon: '🏰' },
  { name: '武汉', icon: '🌉' },
]

onShow(() => {
  fetchExhibitions()
})

async function fetchExhibitions(city?: string) {
  loading.value = true
  try {
    const params: Record<string, any> = { page: 1, page_size: 6, status: 'published' }
    if (city) {
      params.search = city
    }
    const res = await exhibitionApi.getList(params)
    exhibitions.value = res.list || res.items || res.results || []
  } catch (err) {
    console.error('Failed to load exhibitions:', err)
    exhibitions.value = []
  } finally {
    loading.value = false
  }
}

function handleSearch(value: string) {
  const q = (value || '').trim()
  if (!q) {
    // 以前这里直接 return,点了完全没反应 —— 至少给个提示
    uni.showToast({ title: '请先输入搜索关键词', icon: 'none' })
    return
  }
  // 把搜索词交给展会列表 tab(switchTab 不能带参数,用 storage 中转)
  uni.setStorageSync('search_keyword', q)
  uni.switchTab({
    url: '/pages/exhibitions/list',
    fail: (err) => {
      // 跳转失败也要看得见,别再静默
      console.error('switchTab 到展会列表失败:', err)
      uni.showToast({ title: '跳转失败，请重试', icon: 'none' })
    },
  })
}

function handleCityClick(city: string) {
  if (activeCity.value === city) {
    activeCity.value = ''
    fetchExhibitions()
  } else {
    activeCity.value = city
    fetchExhibitions(city)
  }
}

function goToExhibition(id: number) {
  uni.navigateTo({ url: `/pages/exhibitions/detail?id=${id}` })
}

function goToAll() {
  uni.switchTab({ url: '/pages/exhibitions/list' })
}
</script>

<template>
  <view class="home-market">
    <!-- Hero -->
    <view class="hero-market">
      <text class="hero-title">展会市场</text>
      <text class="hero-subtitle">发现适合你的展会，精准对接商机</text>
      <view class="hero-search">
        <SearchBar
          v-model="searchKeyword"
          placeholder="搜索展会名称、城市、主办方..."
          show-button
          @search="handleSearch"
        />
      </view>
    </view>

    <!-- 热门城市 -->
    <view class="city-section">
      <view class="city-header">
        <text class="city-title">🔥 热门城市</text>
        <text v-if="activeCity" class="city-hint">当前筛选：{{ activeCity }}</text>
      </view>
      <view class="city-tags">
        <view
          v-for="city in hotCities"
          :key="city.name"
          :class="['city-tag', { active: activeCity === city.name }]"
          @click="handleCityClick(city.name)"
        >
          <text class="city-icon">{{ city.icon }}</text>
          <text>{{ city.name }}</text>
        </view>
      </view>
    </view>

    <!-- 推荐展会 -->
    <view class="exhibition-section">
      <view class="section-header">
        <text class="section-title">📋 推荐展会</text>
        <view class="view-all" @click="goToAll">
          <text>查看全部</text>
          <text class="arrow">→</text>
        </view>
      </view>

      <LoadingSkeleton v-if="loading" :lines="4" />

      <EmptyState
        v-else-if="exhibitions.length === 0"
        :message="activeCity ? `${activeCity}暂无推荐展会` : '暂无推荐展会'"
        icon="🎪"
      />

      <view v-else class="exhibition-list">
        <ExpoCard
          v-for="exhibition in exhibitions"
          :key="exhibition.id"
          :exhibition="exhibition"
          @click="goToExhibition(exhibition.id)"
        />
      </view>
    </view>

    <!-- 底部特性栏 -->
    <view class="features-bar">
      <view class="feature-item">
        <text class="feature-icon">🎯</text>
        <view>
          <text class="feature-title">海量展会</text>
          <text class="feature-desc">汇聚全国优质展会资源</text>
        </view>
      </view>
      <view class="feature-item">
        <text class="feature-icon">🤝</text>
        <view>
          <text class="feature-title">精准对接</text>
          <text class="feature-desc">采购需求与展品智能匹配</text>
        </view>
      </view>
      <view class="feature-item">
        <text class="feature-icon">📊</text>
        <view>
          <text class="feature-title">高效管理</text>
          <text class="feature-desc">一站式管理展会全流程</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.hero-market {
  background: linear-gradient(135deg, #1a56db 0%, #2563eb 40%, #4f46e5 100%);
  color: #fff;
  padding: 48rpx 24rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.hero-title {
  font-size: 42rpx;
  font-weight: 800;
  margin-bottom: 8rpx;
}

.hero-subtitle {
  font-size: 28rpx;
  opacity: 0.85;
  margin-bottom: 32rpx;
}

.hero-search {
  width: 100%;
}

.city-section {
  background: #fff;
  padding: 24rpx;
  border-bottom: 1px solid var(--color-border);
}

.city-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.city-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

.city-hint {
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 500;
}

.city-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.city-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--color-border);
  border-radius: 20px;
  background: #fff;
  color: var(--color-text);
  font-size: 14px;
  font-weight: 500;
}

.city-tag.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.city-icon {
  font-size: 16px;
}

.exhibition-section {
  padding: 32rpx 24rpx;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.section-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text);
}

.view-all {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: var(--color-primary);
}

.exhibition-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.features-bar {
  background: #fff;
  padding: 32rpx 24rpx;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.feature-icon {
  font-size: 32px;
  flex-shrink: 0;
}

.feature-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  display: block;
  margin-bottom: 4px;
}

.feature-desc {
  font-size: 13px;
  color: var(--color-text-secondary);
}
</style>
