<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

defineProps<{ exhibitions: any[] }>()
const emit = defineEmits<{ (e: 'goto', id: number): void }>()

const current = ref(0)
let timer: number | null = null

onMounted(() => { timer = window.setInterval(() => { current.value = (current.value + 1) % 3 }, 4000) })
onUnmounted(() => { if (timer) clearInterval(timer) })

function countdown(endDate: string) {
  const diff = new Date(endDate).getTime() - Date.now()
  if (diff <= 0) return '已开幕'
  const d = Math.floor(diff / 86400000)
  return d > 0 ? `距开幕还有 ${d} 天` : '今天开幕'
}
</script>

<template>
  <section class="hero">
    <div class="hero-bg"></div>
    <div class="hero-inner">
      <div class="hero-text">
        <h1 class="hero-title">
          <span class="hero-badge">🔥 重磅来袭</span>
          发现全球顶尖展会<br/>精准对接你的商机
        </h1>
        <p class="hero-sub">汇聚全国200+优质展会 · 5000+展商入驻 · 每日新增100+采购需求</p>
        <div class="hero-actions">
          <button class="btn-hero-primary" @click="$router.push('/exhibitions')">🔍 浏览展会</button>
          <button class="btn-hero-outline" @click="$router.push('/register')">🚀 免费注册</button>
        </div>
      </div>
      <div class="hero-carousel" v-if="exhibitions.length > 0">
        <div class="carousel-track" :style="{ transform: `translateX(-${current * 100}%)` }">
          <div class="carousel-slide" v-for="e in exhibitions.slice(0, 5)" :key="e.id"
               @click="emit('goto', e.id)">
            <div class="slide-img" :style="{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }">
              <img v-if="e.cover_image" :src="e.cover_image" :alt="e.title" />
              <span v-else class="slide-placeholder">🎪</span>
            </div>
            <div class="slide-info">
              <span class="slide-badge">{{ e.status === 'ongoing' ? '进行中' : '即将开幕' }}</span>
              <h3>{{ e.title }}</h3>
              <p>{{ e.location }}</p>
              <span class="slide-countdown">{{ countdown(e.start_date) }}</span>
            </div>
          </div>
        </div>
        <div class="carousel-dots">
          <span v-for="i in Math.min(exhibitions.length, 5)" :key="i"
                :class="{ active: current === i - 1 }" @click="current = i - 1"></span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero {
  position: relative; background: linear-gradient(135deg, #0f172a 0%, #1e293b 40%, #312e81 100%);
  color: #fff; overflow: hidden; padding: 80px 24px 60px;
}
.hero-bg {
  position: absolute; inset: 0;
  background: radial-gradient(circle at 30% 50%, rgba(99,102,241,0.15) 0%, transparent 50%),
              radial-gradient(circle at 70% 20%, rgba(59,130,246,0.1) 0%, transparent 50%);
}
.hero-inner {
  position: relative; max-width: 1200px; margin: 0 auto;
  display: grid; grid-template-columns: 1fr 1fr; gap: 48px; align-items: center;
}
.hero-badge {
  display: inline-block; background: linear-gradient(135deg, #f59e0b, #ef4444);
  padding: 4px 14px; border-radius: 20px; font-size: 13px; font-weight: 700; margin-bottom: 16px;
}
.hero-title { font-size: 42px; font-weight: 800; line-height: 1.25; margin-bottom: 16px; }
.hero-sub { font-size: 16px; opacity: 0.75; margin-bottom: 32px; line-height: 1.6; }
.hero-actions { display: flex; gap: 12px; }
.btn-hero-primary {
  padding: 14px 32px; background: linear-gradient(135deg, #6366f1, #3b82f6);
  border: none; border-radius: 10px; color: #fff; font-size: 16px; font-weight: 600; cursor: pointer;
}
.btn-hero-outline {
  padding: 14px 32px; background: transparent; border: 2px solid rgba(255,255,255,0.3);
  border-radius: 10px; color: #fff; font-size: 16px; font-weight: 600; cursor: pointer;
}
.btn-hero-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(99,102,241,0.4); transition: all 0.2s; }
.btn-hero-outline:hover { border-color: #fff; transition: all 0.2s; }

.hero-carousel { overflow: hidden; border-radius: 16px; background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); }
.carousel-track { display: flex; transition: transform 0.5s ease; }
.carousel-slide { min-width: 100%; cursor: pointer; }
.slide-img { height: 200px; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.slide-img img { width: 100%; height: 100%; object-fit: cover; }
.slide-placeholder { font-size: 64px; }
.slide-info { padding: 16px; }
.slide-badge { font-size: 11px; padding: 2px 10px; border-radius: 10px; background: rgba(99,102,241,0.3); }
.slide-info h3 { font-size: 18px; margin: 8px 0 4px; }
.slide-info p { font-size: 13px; opacity: 0.7; }
.slide-countdown { font-size: 13px; color: #fbbf24; font-weight: 600; display: inline-block; margin-top: 8px; }
.carousel-dots { display: flex; justify-content: center; gap: 8px; padding: 12px; }
.carousel-dots span { width: 24px; height: 4px; border-radius: 2px; background: rgba(255,255,255,0.3); cursor: pointer; }
.carousel-dots span.active { background: #6366f1; width: 32px; }

@media (max-width: 768px) {
  .hero-inner { grid-template-columns: 1fr; }
  .hero-title { font-size: 28px; }
  .hero-carousel { display: none; }
  .hero { padding: 48px 16px 40px; }
}
</style>
