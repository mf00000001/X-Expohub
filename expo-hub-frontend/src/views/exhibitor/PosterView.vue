<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api/index'

const posterData = ref<any>(null)
const loading = ref(true)

const tierLabels: Record<string, string> = { bronze: '🥉 铜牌', silver: '🥈 银牌', gold: '🥇 金牌', diamond: '💎 钻石' }

onMounted(async () => {
  try {
    const res: any = await http.get('/poster/exhibitor')
    posterData.value = res?.data || res
  } catch (e) { console.error(e) } finally { loading.value = false }
})

function downloadPoster() {
  const el = document.querySelector('.poster-card') as HTMLElement
  if (!el) return
  // 简单截图：使用浏览器打印功能转为图片
  window.print()
}

async function sharePoster() {
  const code = posterData.value?.referral_code || ''
  const text = `🏪 欢迎来${posterData.value?.company_name || '我的'}展位看看！\n📍 ExpoHub展商主页\n🔗 邀请码：${code}`
  if (navigator.share) {
    await navigator.share({ title: '展商名片', text })
  } else {
    await navigator.clipboard.writeText(text)
    alert('已复制分享文案！')
  }
}
</script>

<template>
  <div class="page-container poster-page">
    <div class="page-header">
      <h2>📸 展商名片海报</h2>
      <div class="header-actions">
        <button class="btn btn-sm btn-default" @click="downloadPoster">🖨️ 打印海报</button>
        <button class="btn btn-sm btn-primary" @click="sharePoster">📤 分享名片</button>
      </div>
    </div>

    <div v-if="loading" class="card" style="text-align:center;padding:60px">生成中...</div>

    <div v-else-if="posterData" class="poster-card">
      <!-- 顶部 -->
      <div class="poster-header">
        <div class="poster-badge">{{ tierLabels[posterData.exhibitor_tier] || '展商' }}</div>
        <div class="poster-logo" v-if="posterData.logo">
          <img :src="posterData.logo" alt="logo" />
        </div>
        <div v-else class="poster-logo-placeholder">🏪</div>
        <h1 class="poster-company">{{ posterData.company_name }}</h1>
        <p class="poster-domain">{{ posterData.industry_domain }}</p>
        <p class="poster-bio" v-if="posterData.bio">{{ posterData.bio }}</p>
        <p class="poster-position" v-if="posterData.position">{{ posterData.position }}</p>
      </div>

      <!-- 数据 -->
      <div class="poster-stats">
        <div class="poster-stat"><strong>{{ posterData.stats.views }}</strong><span>浏览量</span></div>
        <div class="poster-stat"><strong>{{ posterData.stats.favorites }}</strong><span>收藏</span></div>
        <div class="poster-stat"><strong>{{ posterData.stats.matches }}</strong><span>成功匹配</span></div>
        <div class="poster-stat"><strong>{{ posterData.stats.products }}</strong><span>展品</span></div>
      </div>

      <!-- 展品 -->
      <div class="poster-products" v-if="posterData.products?.length > 0">
        <h3>📦 精选展品</h3>
        <div class="poster-product-grid">
          <div v-for="p in posterData.products" :key="p.name" class="poster-product">
            <div class="pp-img" :style="{background: '#f0f4ff'}">📦</div>
            <span class="pp-name">{{ p.name }}</span>
            <span class="pp-price" v-if="p.price">¥{{ p.price }}</span>
          </div>
        </div>
      </div>

      <!-- 底部 -->
      <div class="poster-footer">
        <div class="poster-qr">
          <span style="font-size:48px">📱</span>
          <span style="font-size:10px;color:#666">扫码查看展位</span>
        </div>
        <div class="poster-footer-text">
          <p><strong>ExpoHub</strong> · 全球展会平台</p>
          <p style="font-size:11px;color:#999">邀请码：{{ posterData.referral_code }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.poster-page { max-width: 520px; margin: 0 auto; }
.header-actions { display: flex; gap: 8px; }

.poster-card {
  background: linear-gradient(135deg, #1e293b 0%, #312e81 50%, #1e293b 100%);
  border-radius: 20px; overflow: hidden; color: #fff; box-shadow: 0 20px 60px rgba(0,0,0,0.15);
}
.poster-header { padding: 32px 24px 20px; text-align: center; }
.poster-badge {
  display: inline-block; padding: 4px 14px; border-radius: 12px;
  background: linear-gradient(135deg, #f59e0b, #ef4444);
  font-size: 12px; font-weight: 700; margin-bottom: 16px;
}
.poster-logo { width: 80px; height: 80px; border-radius: 50%; overflow: hidden; margin: 0 auto 12px; background: rgba(255,255,255,0.1); }
.poster-logo img { width: 100%; height: 100%; object-fit: cover; }
.poster-logo-placeholder { font-size: 48px; margin-bottom: 8px; }
.poster-company { font-size: 24px; font-weight: 800; margin-bottom: 4px; }
.poster-domain { font-size: 14px; opacity: 0.7; }
.poster-bio { font-size: 12px; opacity: 0.6; margin-top: 8px; }
.poster-position { font-size: 13px; opacity: 0.6; }

.poster-stats {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
  padding: 16px 24px; background: rgba(255,255,255,0.05);
}
.poster-stat { text-align: center; }
.poster-stat strong { display: block; font-size: 22px; font-weight: 700; }
.poster-stat span { font-size: 11px; opacity: 0.6; }

.poster-products { padding: 20px 24px; }
.poster-products h3 { font-size: 15px; margin-bottom: 12px; opacity: 0.8; }
.poster-product-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.poster-product { padding: 12px; background: rgba(255,255,255,0.08); border-radius: 10px; text-align: center; }
.pp-img { height: 60px; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-bottom: 6px; font-size: 28px; }
.pp-name { font-size: 13px; display: block; }
.pp-price { font-size: 12px; color: #fbbf24; }

.poster-footer {
  display: flex; align-items: center; gap: 16px; padding: 20px 24px;
  background: rgba(0,0,0,0.3);
}
.poster-qr { text-align: center; }
.poster-footer-text p { margin: 2px 0; font-size: 13px; }

@media print {
  body * { visibility: hidden; }
  .poster-card, .poster-card * { visibility: visible; }
  .poster-card { position: absolute; left: 0; top: 0; width: 100%; box-shadow: none; }
}
</style>
