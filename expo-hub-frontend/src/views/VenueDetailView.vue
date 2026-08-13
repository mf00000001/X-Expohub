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
  <div class="container page-wrapper" style="max-width: 960px">
    <!-- 加载状态 -->
    <div v-if="loading" class="card card-body" style="text-align:center; padding:48px">
      <div class="skeleton-line" style="width:60%; margin:0 auto 12px"></div>
      <div class="skeleton-line" style="width:40%; margin:0 auto"></div>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="card card-body" style="text-align:center; padding:48px">
      <div class="form-error">{{ error }}</div>
      <div class="flex gap-2 justify-center mt-4">
        <button class="btn btn-primary" @click="loadVenue">重试</button>
      </div>
    </div>

    <template v-else-if="venue">
      <!-- Hero 头部 -->
      <div class="venue-hero">
        <div class="hero-inner">
          <button class="hero-back" @click="goBack">← 返回</button>
          <div class="hero-badge">{{ venue.city }}</div>
          <h1 class="hero-title">{{ venue.name }}</h1>
          <div class="hero-sub">{{ venue.area ? `场馆面积约 ${venue.area} 万平方米` : '' }}</div>
        </div>
      </div>

      <!-- 信息卡片区 -->
      <div class="info-grid">
        <div class="info-card">
          <div class="info-icon">📍</div>
          <div>
            <div class="info-label">详细地址</div>
            <div class="info-value">{{ venue.address }}</div>
          </div>
        </div>
        <div class="info-card">
          <div class="info-icon">📐</div>
          <div>
            <div class="info-label">场馆面积</div>
            <div class="info-value">{{ venue.area ? venue.area + ' 万平方米' : '暂无数据' }}</div>
          </div>
        </div>
      </div>

      <!-- 重要信息 -->
      <div class="section-card">
        <h3 class="section-title">📋 重要信息</h3>
        <p class="section-text">{{ venue.important_info || '暂无' }}</p>
      </div>

      <!-- 场馆实景(真实图片) -->
      <div v-if="venue.image_url" class="section-card">
        <h3 class="section-title">📷 场馆实景</h3>
        <div class="plan-wrap">
          <img :src="venue.image_url" :alt="venue.name + ' 实景图'" class="plan-img" @click="planZoomed = !planZoomed" />
          <div class="plan-hint">点击图片放大 / 缩小</div>
        </div>
      </div>

      <!-- 场馆平面图 -->
      <div class="section-card">
        <h3 class="section-title">🗺️ 场馆平面图</h3>
        <div v-if="venue.plan_image" class="plan-wrap">
          <img :src="venue.plan_image" alt="场馆平面图" class="plan-img" @click="planZoomed = !planZoomed" />
          <div class="plan-hint">点击图片放大 / 缩小</div>
        </div>
        <p v-else class="section-text">暂无平面图</p>
      </div>

      <!-- 荣誉信息 -->
      <div class="section-card">
        <h3 class="section-title">🏆 荣誉信息</h3>
        <ul v-if="venue.honors && venue.honors.length" class="honor-list">
          <li v-for="(h, i) in venue.honors" :key="i" class="honor-item">
            <span class="honor-badge">🏅</span>
            <span>{{ h }}</span>
          </li>
        </ul>
        <p v-else class="section-text">暂无荣誉信息</p>
      </div>

      <div class="more-row">
        <button class="btn btn-outline btn-sm" @click="goBack">← 返回</button>
      </div>
    </template>

    <!-- 平面图放大遮罩 -->
    <div v-if="planZoomed" class="plan-overlay" @click="planZoomed = false">
      <img :src="venue?.plan_image" alt="场馆平面图(放大)" class="plan-img-zoomed" />
      <div class="plan-overlay-hint">点击任意位置关闭</div>
    </div>
  </div>
</template>

<style scoped>
/* Hero */
.venue-hero {
  background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 55%, #3b82f6 100%);
  border-radius: 16px;
  padding: 32px 28px;
  color: #fff;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
}
.venue-hero::after {
  content: '';
  position: absolute;
  right: -60px; top: -60px;
  width: 220px; height: 220px;
  background: rgba(255,255,255,0.08);
  border-radius: 50%;
}
.hero-inner { position: relative; z-index: 1; }
.hero-back {
  background: rgba(255,255,255,0.15);
  border: none; color: #fff;
  border-radius: 8px; padding: 6px 14px;
  cursor: pointer; font-size: 14px;
  margin-bottom: 18px;
}
.hero-back:hover { background: rgba(255,255,255,0.25); }
.hero-badge {
  display: inline-block;
  background: rgba(255,255,255,0.2);
  border: 1px solid rgba(255,255,255,0.4);
  border-radius: 999px;
  padding: 3px 14px;
  font-size: 13px;
  margin-bottom: 10px;
}
.hero-title { font-size: 30px; font-weight: 700; margin: 0 0 8px; }
.hero-sub { font-size: 15px; opacity: 0.9; }

/* 信息卡片 */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 16px;
}
@media (max-width: 640px) { .info-grid { grid-template-columns: 1fr; } }
.info-card {
  display: flex; gap: 14px; align-items: flex-start;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 18px;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}
.info-icon { font-size: 22px; line-height: 1.4; }
.info-label { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.info-value { font-weight: 600; color: #1f2937; line-height: 1.6; }

/* 区块卡片 */
.section-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px 22px;
  margin-bottom: 16px;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}
.section-title {
  font-size: 17px; font-weight: 700; color: #1f2937;
  margin: 0 0 14px;
  padding-left: 10px;
  border-left: 4px solid #2563eb;
}
.section-text {
  color: #4b5563; line-height: 1.9;
  margin: 0; white-space: pre-wrap;
}

/* 平面图 */
.plan-wrap { cursor: zoom-in; }
.plan-img {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
}
.plan-hint { font-size: 12px; color: #94a3b8; margin-top: 8px; text-align: center; }
.plan-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.8);
  display: flex; align-items: center; justify-content: center;
  cursor: zoom-out;
}
.plan-img-zoomed {
  max-width: 92vw; max-height: 88vh;
  background: #fff; border-radius: 10px;
}
.plan-overlay-hint {
  position: absolute; bottom: 24px; left: 0; right: 0;
  text-align: center; color: #fff; font-size: 13px; opacity: 0.8;
}

/* 荣誉 */
.honor-list { list-style: none; padding: 0; margin: 0; }
.honor-item {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 14px;
  margin-bottom: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  color: #334155;
  font-size: 14px;
  transition: all .2s;
}
.honor-item:hover { border-color: #93c5fd; box-shadow: 0 2px 8px rgb(37 99 235 / 0.08); }
.honor-badge { font-size: 16px; }

.more-row { text-align: center; margin-top: 8px; }

/* 骨架屏 */
.skeleton-line {
  height: 16px; border-radius: 8px;
  background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
@keyframes shimmer { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }
</style>
