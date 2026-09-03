<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
import ExpoCard from '@/components/ExpoCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'

const router = useRouter()
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

onMounted(() => {
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
    exhibitions.value = res.items || res.results || res.data || []
  } catch (err) {
    console.error('Failed to load exhibitions:', err)
    exhibitions.value = []
  } finally {
    loading.value = false
  }
}

function handleSearch(value: string) {
  const q = value.trim()
  if (q) {
    router.push({ name: 'exhibition-list', query: { search: q } })
  }
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
  router.push({ name: 'exhibition-detail', params: { id } })
}

function goToAll() {
  router.push({ name: 'exhibition-list' })
}
</script>

<template>
  <div class="home-market">
    <NavBar />

    <!-- Hero: 展会市场 -->
    <section class="hero-market">
      <div class="container">
        <div class="hero-content">
          <h1 class="hero-title">展会市场</h1>
          <p class="hero-subtitle">发现适合你的展会，精准对接商机</p>
          <div class="hero-search">
            <SearchBar
              v-model="searchKeyword"
              placeholder="搜索展会名称、城市、主办方..."
              @search="handleSearch"
            />
          </div>
        </div>
      </div>
    </section>

    <!-- 热门城市 -->
    <section class="city-section">
      <div class="container">
        <div class="city-header">
          <h3 class="city-title">🔥 热门城市</h3>
          <span class="city-hint" v-if="activeCity">当前筛选：{{ activeCity }}</span>
        </div>
        <div class="city-tags">
          <button
            v-for="city in hotCities"
            :key="city.name"
            :class="['city-tag', { active: activeCity === city.name }]"
            @click="handleCityClick(city.name)"
          >
            <span class="city-icon">{{ city.icon }}</span>
            <span>{{ city.name }}</span>
          </button>
        </div>
      </div>
    </section>

    <!-- 推荐展会 -->
    <section class="exhibition-section">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">📋 推荐展会</h2>
          <button class="btn btn-outline btn-sm" @click="goToAll">
            查看全部 <span class="arrow">→</span>
          </button>
        </div>

        <LoadingSkeleton v-if="loading" :lines="4" />

        <EmptyState
          v-else-if="exhibitions.length === 0"
          :message="activeCity ? `${activeCity}暂无推荐展会` : '暂无推荐展会'"
          icon="🎪"
        />

        <div v-else class="exhibition-grid">
          <ExpoCard
            v-for="exhibition in exhibitions"
            :key="exhibition.id"
            :exhibition="exhibition"
            @click="goToExhibition(exhibition.id)"
          />
        </div>
      </div>
    </section>

    <!-- 底部特性栏 -->
    <section class="features-bar">
      <div class="container">
        <div class="features-row">
          <div class="feature-item">
            <span class="feature-icon">🎯</span>
            <div>
              <h4>海量展会</h4>
              <p>汇聚全国优质展会资源</p>
            </div>
          </div>
          <div class="feature-item">
            <span class="feature-icon">🤝</span>
            <div>
              <h4>精准对接</h4>
              <p>采购需求与展品智能匹配</p>
            </div>
          </div>
          <div class="feature-item">
            <span class="feature-icon">📊</span>
            <div>
              <h4>高效管理</h4>
              <p>一站式管理展会全流程</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* Hero */
.hero-market {
  background: linear-gradient(135deg, #1a56db 0%, #2563eb 40%, #4f46e5 100%);
  color: #fff;
  padding: 72px 16px 56px;
  text-align: center;
  position: relative;
  overflow: hidden;
}

.hero-market::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle at 30% 50%, rgba(255,255,255,0.08) 0%, transparent 50%),
              radial-gradient(circle at 70% 50%, rgba(255,255,255,0.05) 0%, transparent 50%);
  pointer-events: none;
}

.hero-content {
  position: relative;
  z-index: 1;
}

.hero-title {
  font-size: 42px;
  font-weight: 800;
  margin-bottom: 10px;
  letter-spacing: -0.5px;
}

.hero-subtitle {
  font-size: 17px;
  opacity: 0.85;
  margin-bottom: 36px;
  font-weight: 400;
}

.hero-search {
  max-width: 600px;
  margin: 0 auto;
}

/* 热门城市 */
.city-section {
  background: var(--color-white);
  padding: 24px 16px;
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
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--color-border);
  border-radius: 20px;
  background: var(--color-white);
  color: var(--color-text);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.city-tag:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: #eff6ff;
}

.city-tag.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.city-icon {
  font-size: 16px;
}

/* 推荐展会 */
.exhibition-section {
  padding: 40px 16px 48px;
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

.arrow {
  margin-left: 2px;
}

.exhibition-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
}

@media (min-width: 640px) {
  .exhibition-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  .exhibition-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* 底部特性栏 */
.features-bar {
  background: var(--color-white);
  padding: 36px 16px;
  border-top: 1px solid var(--color-border);
}

.features-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
}

@media (min-width: 640px) {
  .features-row {
    grid-template-columns: repeat(3, 1fr);
  }
}

.feature-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.feature-item .feature-icon {
  font-size: 32px;
  flex-shrink: 0;
  margin-top: 2px;
}

.feature-item h4 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--color-text);
}

.feature-item p {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
}

/* Responsive hero */
@media (max-width: 640px) {
  .hero-title {
    font-size: 30px;
  }
  .hero-subtitle {
    font-size: 15px;
  }
  .hero-market {
    padding: 52px 16px 40px;
  }
}
</style>
