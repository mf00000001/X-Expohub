<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { catalogApi, type CatalogProduct } from '@/api/catalog'
import { categoryImage } from '@/utils/categoryImage'

/**
 * 首页「热门展品」区块
 *
 * 数据口径：catalogApi.getProducts({ page_size: 8 })，顺序即接口返回顺序，前端不重排、不补造。
 * 状态约定：加载中显示轻骨架；接口失败或 list 为空时整块（含标题）不渲染。
 * 图片：有真实图就出图；无图或破图时用「该品类的几何占位图」（/categories/<slug>.png），
 *      分类图本身加载失败才退回深蓝渐变 + 品名首字——任何一层都不出现浏览器破图图标。
 */
const PAGE_SIZE = 8

const items = ref<CatalogProduct[]>([])
const total = ref(0)
const loading = ref(true)
/** 图片加载失败过的展品 id（失败后不再重试同一个 src，避免闪烁） */
const broken = ref<Record<number, boolean>>({})
/** 分类占位图是否加载失败过（本地静态图，理论上不会失败；失败则全体退回渐变） */
const coverBroken = ref(false)

/** 数量文案：≥10000 折成「7.1 万」，其余用千分位 */
function formatCount(n: unknown, unit: string): string {
  const v = typeof n === 'number' && Number.isFinite(n) && n > 0 ? Math.round(n) : 0
  if (v >= 10000) return `${(v / 10000).toFixed(1).replace(/\.0$/, '')} 万${unit}`
  return `${v.toLocaleString('zh-CN')} ${unit}`
}

const subText = computed(() => {
  if (total.value > 0) return `已收录 ${formatCount(total.value, '件展品')}`
  return ''
})

/** 有可用图片地址且没失败过 */
function showImage(p: CatalogProduct): boolean {
  const src = typeof p?.image === 'string' ? p.image.trim() : ''
  return src.length > 0 && !broken.value[p.id]
}

/** 兜底首字：按 Unicode 码点取，避免把 emoji / 生僻字截成半个字 */
function firstChar(p: CatalogProduct): string {
  const name = typeof p?.name === 'string' ? p.name.trim() : ''
  const chars = Array.from(name)
  return chars.length > 0 ? chars[0] : '📦'
}

function markBroken(p: CatalogProduct) {
  broken.value = { ...broken.value, [p.id]: true }
}

onMounted(async () => {
  try {
    const res = await catalogApi.getProducts({ page_size: PAGE_SIZE })
    const list = Array.isArray(res?.list) ? res.list : []
    items.value = list.filter(
      (it): it is CatalogProduct =>
        !!it && typeof it.id === 'number' && Number.isFinite(it.id) && typeof it.name === 'string' && !!it.name.trim(),
    )
    const t = Number(res?.total)
    total.value = Number.isFinite(t) && t > 0 ? Math.round(t) : items.value.length
  } catch {
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <!-- 接口失败 / list 为空 → 整块连标题一起不渲染；加载中 → 轻骨架 -->
  <section class="cat-section" v-if="loading || items.length > 0" aria-labelledby="hot-products-title">
    <div class="cat-head">
      <div class="cat-heading">
        <h2 id="hot-products-title">📦 热门展品</h2>
        <p class="cat-sub" v-if="subText">{{ subText }}</p>
      </div>
      <router-link class="cat-more" to="/catalog/products">查看全部 →</router-link>
    </div>

    <!-- 加载中：8 张轻骨架（4:3 图位 + 两行文字） -->
    <div class="pd-grid" v-if="loading" aria-hidden="true">
      <div class="pd-card pd-card--sk" v-for="i in PAGE_SIZE" :key="'sk-' + i">
        <div class="pd-media sk-media"></div>
        <div class="pd-body">
          <div class="sk-line sk-line--title"></div>
          <div class="sk-line sk-line--meta"></div>
        </div>
      </div>
    </div>

    <!-- 有数据：整卡为链接 -->
    <div class="pd-grid" v-else>
      <router-link
        v-for="p in items"
        :key="p.id"
        class="pd-card"
        :to="`/catalog/products/${p.id}`"
        :title="p.name"
      >
        <div class="pd-media">
          <img
            v-if="showImage(p)"
            class="pd-img"
            :src="String(p.image)"
            :alt="p.name"
            loading="lazy"
            @error="markBroken(p)"
          />
          <!-- 无图 / 破图兜底：先用该品类的几何占位图；连占位图都失败才退回深蓝渐变 + 首字 -->
          <div v-else class="pd-fallback">
            <img
              v-if="!coverBroken"
              class="pd-cover"
              :src="categoryImage(p.category)"
              alt=""
              aria-hidden="true"
              loading="lazy"
              decoding="async"
              @error="coverBroken = true"
            />
            <span v-else class="pd-initial" aria-hidden="true">{{ firstChar(p) }}</span>
          </div>
        </div>
        <div class="pd-body">
          <h3 class="pd-name">{{ p.name }}</h3>
          <span class="pd-cat" v-if="p.category">{{ p.category }}</span>
          <p class="pd-ex" v-if="p.exhibitor_name" :title="p.exhibitor_name">{{ p.exhibitor_name }}</p>
        </div>
      </router-link>
    </div>
  </section>
</template>

<style scoped>
.cat-section { margin-bottom: var(--space-7); }
.cat-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}
.cat-heading { min-width: 0; }
.cat-head h2 {
  font-size: var(--font-h2);
  line-height: var(--line-h2);
  font-weight: var(--weight-h2);
  color: var(--ink-900);
  letter-spacing: -0.01em;
}
.cat-sub {
  margin-top: var(--space-1);
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: var(--ink-500);
  font-variant-numeric: tabular-nums;
}
.cat-more {
  flex-shrink: 0;
  font-size: var(--font-sm);
  font-weight: 600;
  color: var(--brand-600);
  transition: color 0.15s ease;
}
.cat-more:hover { color: var(--brand-800); }

/* 桌面 4 列 / 平板 3 列 / 手机 2 列 */
.pd-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
}

.pd-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  color: var(--ink-900);
  transition: box-shadow 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}
.pd-card:hover,
.pd-card:focus-visible {
  box-shadow: var(--shadow-hover);
  border-color: var(--brand-300);
  color: var(--ink-900);
  transform: translateY(-2px);
}

/* 图位固定 4:3，无论有无图都不跳动 */
.pd-media {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  background: var(--surface-2);
}
.pd-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.pd-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, var(--brand-700) 0%, var(--brand-950) 100%);
}
/* 品类占位图：铺满 4:3 图位，与真实照片同一套裁切规则 */
.pd-cover {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.pd-initial {
  font-size: var(--font-h1);
  line-height: 1;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.92);
  letter-spacing: 0.02em;
}

.pd-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-4) var(--space-4);
}
.pd-name {
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  font-weight: 700;
  color: var(--ink-900);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pd-cat {
  align-self: flex-start;
  max-width: 100%;
  padding: 1px var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--font-xs);
  line-height: var(--line-xs);
  color: var(--brand-600);
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 展商名：小字，贴卡片底部，单行截断 */
.pd-ex {
  margin-top: auto;
  padding-top: var(--space-1);
  font-size: var(--font-xs);
  line-height: var(--line-xs);
  color: var(--ink-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 轻骨架 */
.pd-card--sk { pointer-events: none; }
.sk-media {
  border-radius: 0;
  background: linear-gradient(
    90deg,
    var(--surface-2) 25%,
    var(--surface-1) 50%,
    var(--surface-2) 75%
  );
  background-size: 200% 100%;
  animation: pd-shimmer 1.4s ease-in-out infinite;
}
.sk-line {
  border-radius: var(--radius-sm);
  background: linear-gradient(
    90deg,
    var(--surface-2) 25%,
    var(--surface-1) 50%,
    var(--surface-2) 75%
  );
  background-size: 200% 100%;
  animation: pd-shimmer 1.4s ease-in-out infinite;
}
.sk-line--title { width: 82%; height: 16px; }
.sk-line--meta { width: 46%; height: 12px; margin-top: auto; }

@keyframes pd-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .sk-line,
  .sk-media { animation: none; }
  .pd-card:hover,
  .pd-card:focus-visible { transform: none; }
}

@media (max-width: 1024px) {
  .pd-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .pd-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
  .pd-body { padding: var(--space-2) var(--space-3) var(--space-3); }
  .pd-initial { font-size: var(--font-h2); }
}
</style>
