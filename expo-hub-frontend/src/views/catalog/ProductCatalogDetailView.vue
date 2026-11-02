<script setup lang="ts">
/**
 * 展品详情（公开只读）
 *
 * 数据来自 /catalog/products/:id；catalogApi 失败/不存在时返回 null。
 *
 * 安全约定：detail_html 一律用 DOMParser 清洗成纯文本后再交给 {{ }} 插值，
 * 页面内不写入任何 HTML 片段，因此后端即便回传 <script>/<img onerror> 也不会被执行。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { catalogApi, type CatalogProductDetail } from '@/api/catalog'
import { categoryImage } from '@/utils/categoryImage'

const route = useRoute()

const detail = ref<CatalogProductDetail | null>(null)
const loading = ref(true)
const failed = ref(false)
/** 主图加载失败：回退到「品类示意图」，避免破图 */
const imageBroken = ref(false)
/** 品类示意图自身加载失败（本地静态图）：再退回首字水印 */
const coverBroken = ref(false)

const imageSrc = computed<string>(() => (detail.value?.image || '').toString().trim())

/** 展品详情纯文本（去标签后的结果） */
const detailText = computed(() => toPlainText(detail.value?.detail_html))

const exhibitorId = computed<number>(() => {
  const fromRelation = Number(detail.value?.exhibitor?.id)
  if (Number.isFinite(fromRelation) && fromRelation > 0) return fromRelation
  const fromField = Number(detail.value?.exhibitor_id)
  return Number.isFinite(fromField) && fromField > 0 ? fromField : 0
})

const exhibitorName = computed(() => {
  const name = detail.value?.exhibitor?.name || detail.value?.exhibitor_name || ''
  return name.toString().trim()
})

const exhibitorMeta = computed(() => {
  const ex = detail.value?.exhibitor
  const parts: string[] = []
  if (ex?.industry) parts.push(String(ex.industry))
  if (ex?.city) parts.push(String(ex.city))
  if (ex?.expo_name) parts.push(String(ex.expo_name))
  return parts.length ? parts.join(' · ') : '展商资料来自公开名录'
})

function orDash(value?: string | number | null): string {
  const text = (value ?? '').toString().trim()
  return text || '—'
}

/** 名称首字水印（无图时占位用） */
function firstChar(name?: string | null): string {
  const text = (name ?? '').trim()
  return text ? Array.from(text)[0] : '展'
}

/**
 * HTML → 纯文本。
 * 1) DOMParser 解析成文档，先摘掉 script/style/iframe 等可执行或嵌入节点；
 * 2) <br> 换成换行，块级节点末尾补换行，尽量保住原文分段；
 * 3) 取 body.textContent（浏览器已解码实体）；
 * 4) DOMParser 不可用或抛错时，退回「正则去标签 + 实体解码」。
 * 输出始终是字符串，交给模板插值（自动转义），不做任何 DOM HTML 注入。
 */
function toPlainText(input?: string | null): string {
  const raw = (input ?? '').toString()
  if (!raw.trim()) return ''

  try {
    if (typeof DOMParser !== 'undefined') {
      const doc = new DOMParser().parseFromString(raw, 'text/html')
      doc.querySelectorAll('script, style, noscript, template, iframe, object, embed').forEach((el) => el.remove())
      doc.querySelectorAll('br').forEach((el) => el.replaceWith('\n'))
      doc
        .querySelectorAll('p, div, li, h1, h2, h3, h4, h5, h6, tr, section, table')
        .forEach((el) => el.append('\n'))
      return normalizeText(doc.body?.textContent || '')
    }
  } catch {
    // 解析失败走正则兜底
  }

  const withoutTags = raw.replace(/<script[\s\S]*?<\/script>/gi, ' ').replace(/<[^>]*>/g, ' ')
  return normalizeText(decodeEntities(withoutTags))
}

function decodeEntities(text: string): string {
  return text
    .replace(/&nbsp;/gi, ' ')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#0*39;|&apos;/gi, "'")
    .replace(/&amp;/gi, '&')
}

/** 压掉多余空白，保留段落换行 */
function normalizeText(text: string): string {
  return text
    .replace(/\r\n?/g, '\n')
    .replace(/[ \t\f\v]+/g, ' ')
    .replace(/ *\n */g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

async function load(): Promise<void> {
  const id = Number(route.params.id)
  loading.value = true
  failed.value = false
  imageBroken.value = false
  coverBroken.value = false

  if (!Number.isFinite(id) || id <= 0) {
    detail.value = null
    failed.value = true
    loading.value = false
    return
  }

  try {
    const res = await catalogApi.getProduct(id)
    if (!res) {
      detail.value = null
      failed.value = true
      return
    }
    detail.value = res
  } catch {
    detail.value = null
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})

watch(
  () => route.params.id,
  (next, prev) => {
    if (next !== prev) void load()
  },
)
</script>

<template>
  <div class="page">
    <nav class="crumbs" aria-label="面包屑">
      <router-link class="crumb-link" to="/">首页</router-link>
      <span class="crumb-sep">/</span>
      <router-link class="crumb-link" :to="{ name: 'catalog-products' }">展品库</router-link>
      <span class="crumb-sep">/</span>
      <span class="crumb-current">{{ detail?.name || '展品详情' }}</span>
    </nav>

    <!-- 加载中 -->
    <div v-if="loading" class="detail-grid" aria-busy="true" aria-label="加载中">
      <div class="sk-media"></div>
      <div class="sk-lines">
        <div class="sk-line sk-line-lg"></div>
        <div class="sk-line"></div>
        <div class="sk-line sk-line-sm"></div>
      </div>
    </div>

    <!-- 失败 / 不存在 -->
    <div v-else-if="failed || !detail" class="state">
      <p class="state-title">加载失败，点击重试</p>
      <p class="state-text">这件展品的资料暂时没有取到，也可能已从展品库移除。</p>
      <div class="state-actions">
        <button type="button" class="primary-btn" @click="load">重试</button>
        <router-link class="ghost-btn" :to="{ name: 'catalog-products' }">返回展品库</router-link>
      </div>
    </div>

    <template v-else>
      <div class="detail-grid">
        <!-- 左：大图 / 渐变兜底 -->
        <div class="media">
          <img
            v-if="imageSrc && !imageBroken"
            class="media-img"
            :src="imageSrc"
            :alt="detail.name"
            @error="imageBroken = true"
          />
          <div v-else class="media-fallback">
            <img
              v-if="!coverBroken"
              class="media-cover"
              :src="categoryImage(detail.category)"
              alt=""
              aria-hidden="true"
              decoding="async"
              @error="coverBroken = true"
            />
            <span v-else class="media-watermark" aria-hidden="true">{{ firstChar(detail.name) }}</span>
            <!-- 明确标注这是品类示意图而非实拍图，避免买家误以为是产品照片 -->
            <span class="media-hint">暂无实拍图 · 品类示意图</span>
          </div>
        </div>

        <!-- 右：名称 / 分类 / 应用领域 / 规格 -->
        <div class="info">
          <h1 class="info-title">{{ detail.name }}</h1>

          <div class="info-tags">
            <span v-if="detail.category" class="pill pill-strong">{{ detail.category }}</span>
            <span v-if="detail.expo_name" class="pill">{{ detail.expo_name }}</span>
          </div>

          <dl class="spec-list">
            <div class="spec-row">
              <dt>分类</dt>
              <dd>{{ orDash(detail.category) }}</dd>
            </div>
            <div class="spec-row">
              <dt>应用领域</dt>
              <dd>{{ orDash(detail.application) }}</dd>
            </div>
            <div class="spec-row">
              <dt>规格</dt>
              <dd>{{ orDash(detail.price_spec) }}</dd>
            </div>
            <div class="spec-row">
              <dt>展会</dt>
              <dd>{{ orDash(detail.expo_name) }}</dd>
            </div>
            <div class="spec-row">
              <dt>展商</dt>
              <dd>{{ orDash(exhibitorName) }}</dd>
            </div>
          </dl>
        </div>
      </div>

      <!-- 展品详情：纯文本渲染 -->
      <section class="section">
        <h2 class="section-title">展品详情</h2>
        <p v-if="detailText" class="section-text detail-text">{{ detailText }}</p>
        <p v-else class="section-text muted">暂无详情描述</p>
      </section>

      <!-- 所属展商 -->
      <section class="section">
        <h2 class="section-title">所属展商</h2>
        <!-- 名录页已下线并与微展位合并，这里只做静态展示，不再跳转 -->
        <div v-if="exhibitorName" class="exhibitor-card exhibitor-card--static">
          <div class="exhibitor-main">
            <strong class="exhibitor-name">{{ orDash(exhibitorName) }}</strong>
            <span class="exhibitor-meta">{{ exhibitorMeta }}</span>
          </div>
        </div>
        <p v-else class="section-empty">这件展品暂未关联展商信息</p>
      </section>

      <div class="foot-actions">
        <router-link class="ghost-btn" :to="{ name: 'catalog-products' }">← 返回展品库</router-link>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-5) var(--space-5) var(--space-8);
}

/* 面包屑 */
.crumbs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  font-size: var(--font-xs);
  color: var(--ink-500);
}
.crumb-link {
  color: var(--ink-500);
  text-decoration: none;
}
.crumb-link:hover {
  color: var(--brand-600);
}
.crumb-sep {
  color: var(--ink-300);
}
.crumb-current {
  color: var(--ink-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 24rem;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  gap: var(--space-6);
  align-items: start;
}

/* 左侧大图 */
.media {
  position: relative;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: var(--radius-card);
  border: 1px solid var(--ink-100);
  background: var(--surface-2);
  box-shadow: var(--shadow-card);
}
.media-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: var(--surface-1);
  display: block;
}
.media-fallback {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  background: linear-gradient(135deg, var(--brand-900) 0%, var(--brand-600) 100%);
}
/* 品类示意图：铺满 4:3 图位，与真实主图位置一致 */
.media-cover {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.media-watermark {
  font-size: 120px;
  line-height: 1;
  font-weight: var(--weight-h1);
  color: var(--surface-0);
  opacity: 0.22;
  user-select: none;
}
/* 说明胶囊：压在示意图左下角，保证「这是示意图」在任何底色上都读得清 */
.media-hint {
  position: absolute;
  left: var(--space-3);
  bottom: var(--space-3);
  padding: 4px var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--font-xs);
  line-height: 1.6;
  color: var(--surface-0);
  background: rgba(0, 0, 0, 0.38);
  backdrop-filter: blur(2px);
}

/* 右侧信息 */
.info {
  min-width: 0;
}
.info-title {
  font-size: var(--font-h2);
  line-height: var(--line-h2);
  font-weight: var(--weight-h2);
  color: var(--ink-900);
  letter-spacing: -0.01em;
  word-break: break-word;
}
.info-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.pill {
  display: inline-block;
  padding: 3px var(--space-3);
  border-radius: var(--radius-full);
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  color: var(--ink-700);
  font-size: var(--font-xs);
  line-height: 1.6;
}
.pill-strong {
  background: var(--brand-50);
  border-color: var(--brand-100);
  color: var(--brand-600);
  font-weight: 600;
}

.spec-list {
  margin-top: var(--space-5);
  border-top: 1px solid var(--ink-100);
}
.spec-row {
  display: grid;
  grid-template-columns: 5.5rem minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--ink-100);
}
.spec-row dt {
  font-size: var(--font-sm);
  color: var(--ink-500);
}
.spec-row dd {
  font-size: var(--font-sm);
  color: var(--ink-900);
  word-break: break-word;
}

/* 区块 */
.section {
  margin-top: var(--space-6);
  padding: var(--space-5);
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}
.section-title {
  font-size: var(--font-h3);
  line-height: var(--line-h3);
  font-weight: var(--weight-h3);
  color: var(--ink-900);
}
.section-text {
  margin-top: var(--space-3);
  font-size: var(--font-body);
  line-height: var(--line-body);
  color: var(--ink-700);
}
/* 纯文本里保留后端的分段换行 */
.detail-text {
  white-space: pre-wrap;
  word-break: break-word;
}
.muted {
  color: var(--ink-500);
}
.section-empty {
  margin-top: var(--space-4);
  padding: var(--space-5);
  text-align: center;
  font-size: var(--font-sm);
  color: var(--ink-500);
  background: var(--surface-1);
  border: 1px dashed var(--ink-100);
  border-radius: var(--radius-md);
}

/* 所属展商卡片 */
.exhibitor-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-top: var(--space-4);
  padding: var(--space-4);
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  border-radius: var(--radius-md);
  color: inherit;
  text-decoration: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.exhibitor-card--static { cursor: default; }
.exhibitor-card:hover {
  border-color: var(--brand-300);
  box-shadow: var(--shadow-card);
  color: inherit;
}
.exhibitor-card:focus-visible {
  outline: 2px solid var(--brand-500);
  outline-offset: 2px;
}
.exhibitor-main {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}
.exhibitor-name {
  font-size: var(--font-body);
  color: var(--ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.exhibitor-meta {
  font-size: var(--font-xs);
  color: var(--ink-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.exhibitor-go {
  flex-shrink: 0;
  font-size: var(--font-sm);
  font-weight: 600;
  color: var(--brand-600);
}

.foot-actions {
  margin-top: var(--space-5);
  text-align: center;
}

/* 骨架 */
.sk-media {
  aspect-ratio: 4 / 3;
  border-radius: var(--radius-card);
  background: linear-gradient(
    90deg,
    var(--surface-2) 25%,
    var(--surface-1) 50%,
    var(--surface-2) 75%
  );
  background-size: 200% 100%;
  animation: sk-shimmer 1.3s ease-in-out infinite;
}
.sk-lines {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.sk-line {
  height: 18px;
  width: 70%;
  border-radius: var(--radius-md);
  background: linear-gradient(
    90deg,
    var(--surface-2) 25%,
    var(--surface-1) 50%,
    var(--surface-2) 75%
  );
  background-size: 200% 100%;
  animation: sk-shimmer 1.3s ease-in-out infinite;
}
.sk-line-lg {
  height: 32px;
  width: 85%;
}
.sk-line-sm {
  width: 40%;
}
@keyframes sk-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .sk-line,
  .sk-media {
    animation: none;
  }
}

/* 失败 / 空态 */
.state {
  padding: var(--space-7) var(--space-4);
  text-align: center;
  background: var(--surface-1);
  border: 1px dashed var(--ink-100);
  border-radius: var(--radius-card);
}
.state-title {
  font-size: var(--font-h3);
  line-height: var(--line-h3);
  font-weight: var(--weight-h3);
  color: var(--ink-900);
}
.state-text {
  margin-top: var(--space-2);
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: var(--ink-500);
}
.state-actions {
  margin-top: var(--space-4);
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.primary-btn {
  display: inline-block;
  padding: 10px var(--space-5);
  border: none;
  border-radius: var(--radius-btn);
  background: var(--brand-700);
  color: var(--surface-0);
  font-size: var(--font-sm);
  font-family: inherit;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.15s ease;
}
.primary-btn:hover {
  background: var(--brand-600);
  color: var(--surface-0);
}
.ghost-btn {
  display: inline-block;
  padding: 10px var(--space-5);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-btn);
  background: var(--surface-0);
  color: var(--ink-700);
  font-size: var(--font-sm);
  text-decoration: none;
  transition: all 0.15s ease;
}
.ghost-btn:hover {
  border-color: var(--brand-500);
  color: var(--brand-600);
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-4);
  }
}
@media (max-width: 640px) {
  .page {
    padding: var(--space-4) var(--space-4) var(--space-7);
  }
  .info-title {
    font-size: var(--font-h3);
    line-height: var(--line-h3);
  }
  .section {
    margin-top: var(--space-4);
    padding: var(--space-4);
  }
  .media-watermark {
    font-size: 88px;
  }
}
</style>
