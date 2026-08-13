<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { venueApi, type Venue } from '@/api/venue'

const router = useRouter()
const venues = ref<Venue[]>([])
const loading = ref(true)
const activeCity = ref('全部')
const sortBy = ref<'area' | 'city'>('area')

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

const sorted = computed(() => {
  let list = venues.value
  if (activeCity.value !== '全部') {
    list = list.filter((v) => v.city === activeCity.value)
  }
  const arr = [...list]
  if (sortBy.value === 'area') {
    arr.sort((a, b) => (b.area || 0) - (a.area || 0))
  } else {
    arr.sort((a, b) => a.city.localeCompare(b.city, 'zh-CN'))
  }
  return arr
})

// 从重要信息提取交通要点(截取)
function trafficHint(v: Venue): string {
  const t = v.important_info || ''
  const idx = t.indexOf('地铁')
  if (idx >= 0) {
    const seg = t.slice(idx, idx + 40)
    return seg.split(/[;；。]/)[0] || seg
  }
  const idx2 = t.indexOf('机场')
  if (idx2 >= 0) return t.slice(idx2, idx2 + 30)
  return ''
}

function chooseVenue(v: Venue) {
  router.push({ name: 'organizer-exhibition-create', query: { venue_id: String(v.id) } })
}

onMounted(loadVenues)
</script>

<template>
  <div class="container page-wrapper">
    <div class="sel-header">
      <div>
        <h1 class="page-title" style="margin-bottom: 4px">展馆选择</h1>
        <p class="text-muted" style="font-size: 14px">按面积从大到小对比全国 {{ venues.length }} 个展馆，挑选适合的办展场地</p>
      </div>
      <div class="sort-group">
        <label class="form-label" style="margin:0">排序</label>
        <select v-model="sortBy" class="form-input" style="width:auto">
          <option value="area">面积从大到小</option>
          <option value="city">按城市</option>
        </select>
      </div>
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

    <div v-if="loading" class="card card-body text-center">加载中...</div>

    <div v-else class="venue-list">
      <div v-for="v in sorted" :key="v.id" class="venue-row" @click="chooseVenue(v)">
        <div class="row-img">
          <img v-if="v.image_url" :src="v.image_url" :alt="v.name" />
          <div v-else class="row-img-placeholder">🏛️</div>
        </div>
        <div class="row-main">
          <div class="row-title">
            <span class="row-name">{{ v.name }}</span>
            <span class="row-city">{{ v.city }}</span>
          </div>
          <div class="row-meta">
            <span class="meta-item">📐 {{ v.area ? v.area + ' 万㎡' : '面积待确认' }}</span>
            <span v-if="trafficHint(v)" class="meta-item">🚇 {{ trafficHint(v) }}</span>
          </div>
          <div class="row-honors">
            <span v-for="(h, i) in (v.honors || []).slice(0, 2)" :key="i" class="honor-tag">🏅 {{ h }}</span>
          </div>
        </div>
        <button class="btn btn-primary btn-sm choose-btn" @click.stop="chooseVenue(v)">选此展馆 →</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sel-header {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 16px; margin-bottom: 16px; flex-wrap: wrap;
}
.sort-group { display: flex; align-items: center; gap: 8px; }

.city-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.chip {
  border: 1px solid #e2e8f0; background: #fff; border-radius: 999px;
  padding: 6px 16px; font-size: 13px; color: #475569; cursor: pointer; transition: all .2s;
}
.chip:hover { border-color: #93c5fd; color: #2563eb; }
.chip-active { background: #2563eb; border-color: #2563eb; color: #fff; font-weight: 500; }

.venue-list { display: flex; flex-direction: column; gap: 12px; }
.venue-row {
  display: flex; align-items: center; gap: 16px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 14px 16px; cursor: pointer; transition: all .2s;
}
.venue-row:hover { border-color: #93c5fd; box-shadow: 0 4px 12px rgb(37 99 235 / 0.1); }
.row-img { flex-shrink: 0; width: 120px; height: 80px; border-radius: 8px; overflow: hidden; background: #f1f5f9; }
.row-img img { width: 100%; height: 100%; object-fit: cover; }
.row-img-placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 28px; }
.row-main { flex: 1; min-width: 0; }
.row-title { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.row-name { font-size: 16px; font-weight: 700; color: #1f2937; }
.row-city {
  background: #eff6ff; color: #2563eb; border-radius: 6px;
  padding: 1px 8px; font-size: 12px; font-weight: 600;
}
.row-meta { display: flex; gap: 14px; flex-wrap: wrap; font-size: 13px; color: #64748b; margin-bottom: 6px; }
.row-honors { display: flex; gap: 6px; flex-wrap: wrap; }
.honor-tag {
  font-size: 12px; color: #b45309; background: #fffbeb;
  border-radius: 6px; padding: 2px 8px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 220px;
}
.choose-btn { flex-shrink: 0; }
@media (max-width: 640px) { .row-img { width: 80px; height: 60px; } .choose-btn { padding: 6px 10px; font-size: 12px; } }
</style>
