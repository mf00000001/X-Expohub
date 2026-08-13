<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { venueApi, type Venue } from '@/api/venue'

const router = useRouter()
const venues = ref<Venue[]>([])
const loading = ref(true)
const activeCity = ref('全部')
const keyword = ref('')

async function loadVenues() {
  loading.value = true
  try {
    const res = await venueApi.getList()
    venues.value = res.list || []
  } catch {
    venues.value = []
  } finally {
    loading.value = false
  }
}

const cities = computed(() => {
  const set = new Set(venues.value.map((v) => v.city))
  return ['全部', ...Array.from(set).sort()]
})

const filtered = computed(() => {
  let list = venues.value
  if (activeCity.value !== '全部') {
    list = list.filter((v) => v.city === activeCity.value)
  }
  const kw = keyword.value.trim()
  if (kw) {
    list = list.filter((v) => v.name.includes(kw) || v.address.includes(kw) || v.city.includes(kw))
  }
  return list
})

onMounted(loadVenues)

function goDetail(id: number) {
  router.push({ name: 'venue-detail', params: { id } })
}
</script>

<template>
  <div class="container page-wrapper">
    <div class="list-header">
      <div>
        <h1 class="page-title" style="margin-bottom: 4px">展馆名录</h1>
        <p class="text-muted" style="font-size: 14px">全国 {{ venues.length }} 个常用会展场馆</p>
      </div>
      <input
        v-model="keyword"
        class="form-input search-input"
        type="text"
        placeholder="🔍 搜索展馆 / 城市 / 地址"
      />
    </div>

    <!-- 城市筛选 -->
    <div class="city-chips">
      <button
        v-for="c in cities"
        :key="c"
        class="chip"
        :class="{ 'chip-active': activeCity === c }"
        @click="activeCity = c"
      >{{ c }}</button>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="grid">
      <div v-for="i in 8" :key="i" class="skeleton-card"></div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="filtered.length === 0" class="empty-state">
      <div style="font-size: 40px; margin-bottom: 12px">🏛️</div>
      <div class="empty-text">未找到匹配的展馆</div>
      <button class="btn btn-outline btn-sm mt-4" @click="activeCity = '全部'; keyword = ''">清除筛选</button>
    </div>

    <!-- 卡片网格 -->
    <div v-else class="grid">
      <div
        v-for="v in filtered"
        :key="v.id"
        class="venue-card"
        @click="goDetail(v.id)"
      >
        <div class="card-top">
          <span class="card-city">{{ v.city }}</span>
          <span class="card-area" v-if="v.area">{{ v.area }}万㎡</span>
        </div>
        <h3 class="card-name">{{ v.name }}</h3>
        <div class="card-addr">📍 {{ v.address }}</div>
        <div class="card-honors" v-if="v.honors && v.honors.length">
          <span v-for="(h, i) in v.honors.slice(0, 2)" :key="i" class="card-honor">🏅 {{ h }}</span>
        </div>
        <div class="card-more">查看详情 →</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.search-input { max-width: 320px; }

/* 城市 chips */
.city-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.chip {
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 999px;
  padding: 6px 16px;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  transition: all .2s;
}
.chip:hover { border-color: #93c5fd; color: #2563eb; }
.chip-active {
  background: #2563eb; border-color: #2563eb; color: #fff;
  font-weight: 500;
}

/* 卡片网格 */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.venue-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 20px;
  cursor: pointer;
  transition: all .25s;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}
.venue-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 20px -4px rgb(37 99 235 / 0.15);
  border-color: #93c5fd;
}
.card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.card-city {
  background: #eff6ff; color: #2563eb;
  border-radius: 6px; padding: 2px 10px;
  font-size: 12px; font-weight: 600;
}
.card-area { font-size: 12px; color: #64748b; }
.card-name { font-size: 17px; font-weight: 700; color: #1f2937; margin: 0 0 8px; }
.card-addr { font-size: 13px; color: #64748b; line-height: 1.6; margin-bottom: 10px; }
.card-honors { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
.card-honor {
  font-size: 12px; color: #b45309; background: #fffbeb;
  border-radius: 6px; padding: 3px 8px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.card-more { font-size: 13px; color: #2563eb; font-weight: 500; }

/* 骨架屏 */
.skeleton-card {
  height: 150px; border-radius: 14px;
  background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
@keyframes shimmer { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }

.empty-state { text-align: center; padding: 60px 0; color: #94a3b8; }
.empty-text { font-size: 15px; }
</style>
