<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { formatStat, type PublicStats } from '@/api/stats'
import ExpoCover from '@/components/ExpoCover.vue'

// Hero 首屏：商务深蓝底 + 金色只做强调（CTA / 数字 / 倒计时徽章）。
// 所有数字来自父组件传入的 /stats/public 与精选展会列表，组件内不请求、不编造。
const props = defineProps<{ exhibitions: any[]; stats?: PublicStats | null }>()
const emit = defineEmits<{ (e: 'goto', id: number): void }>()

/** 轮播上限 5 张：首屏只留焦点，不把全部精选堆上来 */
const MAX_SLIDES = 5

/** 首屏轮播的状态口径：用户视角三态（能去 / 正在开 / 已关门） */
type SlideStatus = 'upcoming' | 'ongoing' | 'ended'

/** 排序权重：即将开幕 → 进行中 → 已结束。已结束只作兜底，不占首屏引流位 */
const STATUS_RANK: Record<SlideStatus, number> = { upcoming: 0, ongoing: 1, ended: 2 }

/**
 * 轮播取数顺序：
 * 1) 有「即将开幕 / 进行中」的展会时，轮播只放这些（已结束不展示）；
 * 2) 全部都已结束时才退回展示已结束，不出现空轮播；
 * 3) 同组按日期排：即将开幕/进行中「越早开始越靠前」，已结束「越近结束越靠前」，
 *    日期缺失的排到同组末尾（缺失不等于今天，不参与猜测）。
 */
const slides = computed<any[]>(() => {
  const rows = (props.exhibitions ?? [])
    .filter((e) => e && typeof e === 'object')
    .map((e, idx) => {
      const start = parseDate(e?.start_date || e?.startDate)
      return { e, idx, status: statusOf(e), ts: start ? start.getTime() : null }
    })

  rows.sort((a, b) => {
    if (STATUS_RANK[a.status] !== STATUS_RANK[b.status]) {
      return STATUS_RANK[a.status] - STATUS_RANK[b.status]
    }
    if (a.ts === null && b.ts === null) return a.idx - b.idx
    if (a.ts === null) return 1
    if (b.ts === null) return -1
    if (a.ts === b.ts) return a.idx - b.idx
    return a.status === 'ended' ? b.ts - a.ts : a.ts - b.ts
  })

  const live = rows.filter((r) => r.status !== 'ended')
  const picked = live.length > 0 ? live : rows
  return picked.slice(0, MAX_SLIDES).map((r) => r.e)
})

/** 三个胶囊要点：与首页区块一一对应（沿用原有文案） */
const points = ['按行业找展品', '收藏展商 · 预约见面', '采购需求直接对接']

/**
 * 副标题：把真实统计数字写成一句人话，而不是三个数字罗列。
 * 数字全部来自 /stats/public，接口失败时退回不带数字的版本（绝不编造）。
 */
const heroSub = computed(() => {
  const s = props.stats
  if (!s) return '挑展会 · 约展商 · 接需求，从看到展位到谈成订单，一条链路走完。'
  // 真实计数为 0 的项直接不念（例如采购需求暂时没有数据时，
  // 否则会出现「0 条采购需求可以接」这种自曝其短的句子）
  const parts: string[] = []
  if (Number(s.exhibitions) > 0) parts.push(`${formatStat(s.exhibitions)} 场展会可以逛`)
  if (Number(s.exhibitors) > 0) parts.push(`${formatStat(s.exhibitors)} 家展商可以约`)
  if (Number(s.products) > 0) parts.push(`${formatStat(s.products)} 件展品可以看`)
  if (Number(s.procurements) > 0) parts.push(`${formatStat(s.procurements)} 条采购需求可以接`)
  return parts.length ? parts.join('，') + '。' : '挑展会 · 约展商 · 接需求，一条链路走完。'
})

/** 首屏底部实时数据带：4 个真实计数，缺失由 formatStat 统一显示「—」 */
const statBand = computed(() => [
  { label: '在展展会', value: formatStat(props.stats?.exhibitions) },
  { label: '入驻展商', value: formatStat(props.stats?.exhibitors) },
  { label: '在架展品', value: formatStat(props.stats?.products) },
  { label: '采购需求', value: formatStat(props.stats?.procurements) },
])

const current = ref(0)
let timer: number | null = null

/** 轮播只对「已加载且多于 1 张」的列表启动：数据异步返回，所以用 watch 重建定时器 */
function restartTimer() {
  if (timer) { clearInterval(timer); timer = null }
  if (slides.value.length <= 1) return
  timer = window.setInterval(() => {
    current.value = (current.value + 1) % slides.value.length
  }, 4000)
}

watch(() => slides.value.length, (n) => {
  if (n > 0 && current.value >= n) current.value = 0
  restartTimer()
})
onMounted(restartTimer)
onUnmounted(() => { if (timer) { clearInterval(timer); timer = null } })

/** 封面字段三种命名都兼容（老数据是 cover_image，新接口可能是 cover_url） */
function coverOf(e: any): string {
  return e?.cover_image || e?.cover_url || e?.cover_image_url || ''
}

/** 日期解析：缺失/非法一律返回 null（不把坏数据当成「今天」） */
function parseDate(value?: string): Date | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isFinite(d.getTime()) ? d : null
}

/**
 * 状态推导：先看结束日期、再看开始日期（用户真正关心的是「还能不能去」）；
 * 两个日期都缺失或非法时，才回退到后端 status 的明确取值，仍不明确则按「即将开幕」占位。
 */
function statusOf(e: any): SlideStatus {
  const now = Date.now()
  const end = parseDate(e?.end_date || e?.endDate)
  const start = parseDate(e?.start_date || e?.startDate)
  if (end && now > end.getTime()) return 'ended'
  if (start && now >= start.getTime()) return 'ongoing'
  if (start) return 'upcoming'
  const st = String(e?.status || '')
  if (st === 'ongoing') return 'ongoing'
  if (st === 'finished' || st === 'ended' || st === 'cancelled') return 'ended'
  return 'upcoming'
}

/** 距开幕天数：日期缺失/非法/已开幕都返回空串，不显示假倒计时 */
function daysLeft(startDate?: string): string {
  if (!startDate) return ''
  const t = new Date(startDate).getTime()
  if (!Number.isFinite(t)) return ''
  const diff = t - Date.now()
  if (diff <= 0) return ''
  const d = Math.floor(diff / 86400000)
  return d > 0 ? `距开幕还有 ${d} 天` : '今天开幕'
}

/**
 * 角标文案：即将开幕显示倒计时（无合法日期时退回「即将开幕」），进行中/已结束用状态词。
 * 配色按状态区分，见样式里的 .slide-status.upcoming / .ongoing / .ended。
 */
function badgeText(e: any): string {
  const st = statusOf(e)
  if (st === 'ended') return '已结束'
  if (st === 'ongoing') return '进行中'
  return daysLeft(e?.start_date || e?.startDate) || '即将开幕'
}
</script>

<template>
  <section class="hero">
    <!-- 右上角极淡金色径向光晕（opacity ≤ 0.18），只做氛围，不抢文字 -->
    <div class="hero-glow" aria-hidden="true"></div>

    <div class="hero-grid">
      <div class="hero-text">
        <span class="hero-badge">🌍 展会 · 展商 · 采购需求</span>
        <!-- 主标题：只描述可核对的动作与结果，不用绝对化用语 -->
        <h1 class="hero-title">找对展会<br />谈成生意</h1>
        <p class="hero-sub">{{ heroSub }}</p>
        <ul class="hero-points">
          <li v-for="p in points" :key="p">{{ p }}</li>
        </ul>
        <div class="hero-actions">
          <!-- 参观登记：注册页默认角色即观众 -->
          <button type="button" class="cta-primary" @click="$router.push('/register')">参观登记</button>
          <!-- 展位申请：注册后可选展商身份，沿用原有入驻入口 -->
          <button type="button" class="cta-ghost" @click="$router.push('/register')">展位申请</button>
        </div>
      </div>

      <!-- 轮播：图上叠加展会名 + 状态角标（即将开幕显示倒计时）；移动端排到文案下方 -->
      <div class="hero-carousel" v-if="slides.length > 0">
        <div class="carousel-viewport">
          <div class="carousel-track" :style="{ transform: `translateX(-${current * 100}%)` }">
            <div class="carousel-slide" v-for="e in slides" :key="e.id"
                 :class="{ clickable: !!e.id }"
                 :role="e.id ? 'link' : undefined"
                 :tabindex="e.id ? 0 : undefined"
                 @click="e.id && emit('goto', e.id)"
                 @keydown.enter="e.id && emit('goto', e.id)">
              <div class="slide-media">
                <!-- 封面：有图出图；cover_image 为空串或图片 404 时由 ExpoCover 落到品牌渐变兜底，不出破图图标 -->
                <ExpoCover class="slide-cover" :src="coverOf(e)" :title="e.title || e.name || ''" ratio="16/9" />
                <!-- 状态角标：文案与配色都按状态区分（即将开幕=金+倒计时 / 进行中=绿 / 已结束=灰） -->
                <span class="slide-status" :class="statusOf(e)">{{ badgeText(e) }}</span>
                <div class="slide-caption">
                  <p class="slide-title">{{ e.title }}</p>
                  <p class="slide-place" v-if="e.location">{{ e.location }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="carousel-dots" v-if="slides.length > 1">
          <button v-for="(s, i) in slides" :key="s.id" type="button"
                  class="dot" :class="{ active: current === i }"
                  :aria-label="`切换到第 ${i + 1} 张展会`" @click="current = i"></button>
        </div>
      </div>
    </div>

    <!-- 实时数据带：数字金色、标签半透明白、1px 竖线分隔 -->
    <div class="hero-stats">
      <div class="hero-stat" v-for="s in statBand" :key="s.label">
        <strong>{{ s.value }}</strong>
        <span>{{ s.label }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  color: var(--surface-0);
  background: linear-gradient(150deg, var(--brand-950) 0%, var(--brand-900) 46%, var(--brand-800) 100%);
  padding: var(--space-8) var(--space-5) var(--space-6);
}
.hero-glow {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(760px 520px at 88% 4%, var(--accent-500) 0%, transparent 62%);
  opacity: 0.16;
}

.hero-grid {
  position: relative;
  max-width: var(--max-width);
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 560px);
  gap: var(--space-7);
  align-items: center;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--font-xs);
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--accent-400);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.14);
}

/* 字号按品牌规格 clamp(32px, 5vw, 56px)，字重 800，字距收紧 */
.hero-title {
  margin-bottom: var(--space-4);
  font-size: clamp(32px, 5vw, 56px);
  font-weight: 800;
  line-height: 1.14;
  letter-spacing: -0.02em;
  color: var(--surface-0);
}

/* 18px = --font-body + 2px，仍由令牌推导，不单独写死字号 */
.hero-sub {
  max-width: 520px;
  margin-bottom: var(--space-5);
  font-size: calc(var(--font-body) + 2px);
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.8);
}

.hero-points {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
  margin-bottom: var(--space-6);
}
.hero-points li {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: calc(var(--font-xs) + 1px);
  color: rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.14);
}
.hero-points li::before {
  content: '✓';
  color: var(--accent-500);
  font-weight: 700;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.cta-primary,
.cta-ghost {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-3) var(--space-6);
  border-radius: var(--radius-btn);
  font-size: var(--font-body);
  font-weight: 700;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}
.cta-primary {
  border: 1px solid var(--accent-500);
  background: var(--accent-500);
  color: var(--brand-950);
}
.cta-primary:hover {
  background: var(--accent-400);
  border-color: var(--accent-400);
}
.cta-ghost {
  border: 1px solid var(--surface-0);
  background: transparent;
  color: var(--surface-0);
}
.cta-ghost:hover {
  background: var(--surface-0);
  color: var(--brand-950);
}

/* ---------- 轮播 ---------- */
.hero-carousel {
  width: 100%;
  max-width: 560px;
  justify-self: end;
}
.carousel-viewport {
  position: relative;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: var(--shadow-dark);
  background: var(--brand-800);
}
.carousel-track {
  display: flex;
  transition: transform 0.5s ease;
}
.carousel-slide {
  min-width: 100%;
  height: 380px;
}
.carousel-slide.clickable { cursor: pointer; }
.carousel-slide:focus-visible {
  outline: 2px solid var(--accent-400);
  outline-offset: -2px;
}

.slide-media {
  position: relative;
  height: 100%;
  background: linear-gradient(150deg, var(--brand-800) 0%, var(--brand-600) 100%);
  overflow: hidden;
}
/* 封面组件撑满轮播位：高度仍由 .carousel-slide 固定，比例交给容器宽度决定 */
.slide-media :deep(.slide-cover) {
  width: 100%;
  height: 100%;
  transition: transform 0.24s ease;
}
.carousel-slide:hover :deep(.slide-cover) { transform: scale(1.02); }
/* 首屏下方已有 slide-caption 展示展会名，兜底封面不再重复一遍左下角标题，避免两行字重叠 */
.slide-media :deep(.cover-name) { display: none; }
/* 深蓝渐变遮罩：保证图上白字可读，颜色走 --brand-950 */
.slide-media::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  background: linear-gradient(180deg, transparent 38%, var(--brand-950) 100%);
  opacity: 0.84;
  pointer-events: none;
}
/* 状态角标：底色即状态语义，统一用品牌令牌，不写死色值 */
.slide-status {
  position: absolute;
  top: var(--space-4);
  left: var(--space-4);
  z-index: 2;
  display: inline-flex;
  align-items: center;
  padding: 2px var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--font-xs);
  font-weight: 700;
  letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums;
  color: var(--brand-950);
  box-shadow: var(--shadow-sm);
}
/* 即将开幕：品牌金底，文案带「距开幕还有 N 天」倒计时 */
.slide-status.upcoming { background: var(--accent-500); }
/* 进行中：绿色系，表示正在发生 */
.slide-status.ongoing { background: var(--success); }
/* 已结束：灰色，只在全部展会都结束时兜底出现 */
.slide-status.ended { background: var(--ink-300); }
.slide-caption {
  position: absolute;
  left: var(--space-5);
  right: var(--space-5);
  bottom: var(--space-5);
  z-index: 2;
}
.slide-title {
  font-size: var(--font-h3);
  font-weight: 700;
  line-height: 1.35;
  color: var(--surface-0);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.slide-place {
  margin-top: var(--space-1);
  font-size: var(--font-xs);
  color: rgba(255, 255, 255, 0.72);
}

.carousel-dots {
  display: flex;
  justify-content: center;
  gap: var(--space-2);
  padding-top: var(--space-3);
}
.dot {
  width: 24px;
  height: 4px;
  padding: 0;
  border: none;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  transition: background 0.18s ease, width 0.18s ease;
}
.dot.active {
  width: 32px;
  background: var(--accent-500);
}
.dot:focus-visible {
  outline: 2px solid var(--accent-400);
  outline-offset: 2px;
}

/* ---------- 底部实时数据带 ---------- */
.hero-stats {
  position: relative;
  max-width: var(--max-width);
  margin: var(--space-7) auto 0;
  padding-top: var(--space-5);
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.hero-stat { text-align: center; }
.hero-stat + .hero-stat { border-left: 1px solid rgba(255, 255, 255, 0.12); }
.hero-stat strong {
  display: block;
  font-size: var(--font-h2);
  font-weight: 800;
  line-height: 1.2;
  color: var(--accent-500);
  font-variant-numeric: tabular-nums;
}
.hero-stat span {
  display: block;
  margin-top: var(--space-1);
  font-size: calc(var(--font-xs) + 1px);
  color: rgba(255, 255, 255, 0.6);
}

@media (max-width: 1024px) {
  .hero-grid { grid-template-columns: minmax(0, 1fr) minmax(0, 440px); gap: var(--space-6); }
  .carousel-slide { height: 320px; }
}

@media (max-width: 768px) {
  .hero { padding: var(--space-6) var(--space-4) var(--space-5); }
  /* 单列：轮播图落到文案下方 */
  .hero-grid { grid-template-columns: 1fr; gap: var(--space-6); }
  .hero-carousel { max-width: none; justify-self: stretch; }
  .carousel-slide { height: 260px; }
  .hero-sub { font-size: var(--font-body); }
  .hero-actions { gap: var(--space-2); }
  .cta-primary, .cta-ghost { flex: 1 1 160px; padding: var(--space-3) var(--space-4); }
  /* 数据带 2×2 换行，只在每行第二格保留竖线 */
  .hero-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: var(--space-4); margin-top: var(--space-6); }
  .hero-stat + .hero-stat { border-left: none; }
  .hero-stat:nth-child(even) { border-left: 1px solid rgba(255, 255, 255, 0.12); }
  .hero-stat strong { font-size: var(--font-h3); }
}
</style>
