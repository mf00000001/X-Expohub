<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { venueApi, type Venue } from '@/api/venue'

const route = useRoute()
const router = useRouter()
const venue = ref<Venue | null>(null)
const loading = ref(true)
const error = ref('')
const planZoomed = ref(false)

async function loadVenue() {
  loading.value = true
  error.value = ''
  try {
    venue.value = await venueApi.getDetail(Number(route.params.id))
    if (!venue.value) {
      error.value = '展馆不存在'
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadVenue)

function goBack() {
  router.back()
}
</script>

<template>
  <div class="container page-wrapper" style="max-width: 900px">
    <div class="flex items-center gap-2 mb-6">
      <button class="btn btn-outline btn-sm" @click="goBack">← 返回</button>
      <h1 class="page-title" style="margin-bottom: 0">展馆信息</h1>
    </div>

    <div v-if="loading" class="card"><div class="card-body">加载中...</div></div>
    <div v-else-if="error" class="card">
      <div class="card-body">
        <div class="form-error">{{ error }}</div>
        <button class="btn btn-primary mt-4" @click="loadVenue">重试</button>
      </div>
    </div>

    <div v-else-if="venue" class="card">
      <div class="card-body">
        <h2 class="text-xl font-bold mb-1">{{ venue.name }}</h2>
        <div class="text-muted mb-4">{{ venue.city }}</div>

        <div class="grid grid-cols-1 grid-cols-2 gap-4 mb-4">
          <div class="info-box">
            <div class="info-label">详细地址</div>
            <div class="info-value">{{ venue.address }}</div>
          </div>
          <div class="info-box">
            <div class="info-label">场馆面积</div>
            <div class="info-value">{{ venue.area ? venue.area + ' 万平方米' : '暂无数据' }}</div>
          </div>
        </div>

        <div class="mb-4">
          <h3 class="font-bold mb-2" style="border-left: 3px solid var(--primary, #2563eb); padding-left: 8px;">重要信息</h3>
          <p class="text-muted" style="line-height: 1.8; white-space: pre-wrap;">{{ venue.important_info || '暂无' }}</p>
        </div>

        <div class="mb-4">
          <h3 class="font-bold mb-2" style="border-left: 3px solid var(--primary, #2563eb); padding-left: 8px;">场馆平面图</h3>
          <div v-if="venue.plan_image" class="plan-wrap">
            <img :src="venue.plan_image" alt="场馆平面图" class="plan-img" @click="planZoomed = !planZoomed" />
            <div class="plan-hint">点击图片放大/缩小</div>
          </div>
          <p v-else class="text-muted">暂无平面图</p>
        </div>

        <div v-if="planZoomed" class="plan-overlay" @click="planZoomed = false">
          <img :src="venue.plan_image" alt="场馆平面图(放大)" class="plan-img-zoomed" />
          <div class="plan-overlay-hint">点击任意位置关闭</div>
        </div>

        <div>
          <h3 class="font-bold mb-2" style="border-left: 3px solid var(--primary, #2563eb); padding-left: 8px;">荣誉信息</h3>
          <ul v-if="venue.honors && venue.honors.length" class="honor-list">
            <li v-for="(h, i) in venue.honors" :key="i" class="honor-item">
              <span class="honor-badge">🏆</span> {{ h }}
            </li>
          </ul>
          <p v-else class="text-muted">暂无荣誉信息</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.info-box {
  background: var(--surface, #f8fafc);
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  padding: 12px 16px;
}
.info-label {
  font-size: 12px;
  color: var(--muted, #64748b);
  margin-bottom: 4px;
}
.info-value {
  font-weight: 500;
}
.honor-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.honor-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 8px;
  background: var(--surface, #f8fafc);
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
}
.honor-badge {
  font-size: 16px;
}
/* 平面图 */
.plan-wrap { cursor: zoom-in; }
.plan-img {
  width: 100%;
  max-width: 640px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: #fff;
}
.plan-hint { font-size: 12px; color: var(--muted, #64748b); margin-top: 4px; }
.plan-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.75);
  display: flex; align-items: center; justify-content: center;
  cursor: zoom-out;
}
.plan-img-zoomed {
  max-width: 92vw; max-height: 88vh;
  background: #fff; border-radius: 8px;
}
.plan-overlay-hint {
  position: absolute; bottom: 20px; left: 0; right: 0;
  text-align: center; color: #fff; font-size: 13px; opacity: 0.8;
}
</style>
