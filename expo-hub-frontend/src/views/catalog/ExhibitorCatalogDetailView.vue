<script setup lang="ts">
/**
 * 展商详情（公开只读）—— 对齐参考站 e.chtf.com/#/exhorDetails/:id 的信息架构
 *
 * 参考站区块 → 本页区块：
 *   面包屑（首页/展商列表/展商详情）      → 同（展商名录）
 *   头部：logo + 公司名 + 浏览量           → CompanyAvatar + 名称/英文名 + 官网
 *   企业介绍（简介 + 公司实景图）          → 企业介绍（description / main_business 纯文本）
 *   联系方式卡（联系人/地址/电话/邮箱）    → 展商信息卡（行业/城市/国家/展位号/企业类型/规模/数据来源）
 *   在线收藏 / 约见洽谈                   → 官网入口 + 返回名录（收藏/约见属平台账号体系，名录展商无账号）
 *   公司产品网格（查看详情）               → 名录展品网格（链到 /catalog/products/:id）
 *
 * 说明：名录是第三方公开快照，没有 logo/联系人/电话/邮箱字段，页面不编造缺失值，
 * 一律「有则显示、无则整行不渲染」，避免出现空标签和破图。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import CompanyAvatar from '@/components/CompanyAvatar.vue'
import { catalogApi, type CatalogExhibitorDetail } from '@/api/catalog'
import { exhibitionApi } from '@/api/exhibition'
import { categoryImage } from '@/utils/categoryImage'

const route = useRoute()

const detail = ref<CatalogExhibitorDetail | null>(null)
const loading = ref(true)
const failed = ref(false)
/** 展品图加载失败的 id：回退到品类占位图，不出现破图 */
const brokenProductIds = ref<number[]>([])

const name = computed(() => (detail.value?.name || '').toString().trim())
const nameEn = computed(() => (detail.value?.name_en || '').toString().trim())
const website = computed(() => (detail.value?.website || '').toString().trim())
const description = computed(() =>
  ((detail.value?.description || detail.value?.main_business || '') as string).toString().trim(),
)
const products = computed(() => detail.value?.products ?? [])

/** 展会 id → 展会标题（只为「所属展会」链接显示可读名字；取不到就退回 #id） */
const exhibitionTitles = ref<Record<number, string>>({})

/** 所属展会：优先关系表口径 exhibition_ids（可能多场），旧后端只有单值则降级 */
const exhibitionIds = computed<number[]>(() => {
  const ids = detail.value?.exhibition_ids
  if (Array.isArray(ids) && ids.length > 0) {
    return ids.map((v) => Number(v)).filter((v) => Number.isFinite(v) && v > 0)
  }
  const single = Number(detail.value?.exhibition_id)
  return Number.isFinite(single) && single > 0 ? [single] : []
})

/** 批量补展会标题（最多 5 场，失败静默退回 #id，不影响正文） */
async function loadExhibitionTitles(ids: number[]): Promise<void> {
  const limited = ids.slice(0, 5)
  if (limited.length === 0) return
  const pairs = await Promise.all(
    limited.map(async (id) => {
      try {
        const info: any = await exhibitionApi.getDetail(id)
        return [id, (info?.title || '').toString().trim()] as const
      } catch {
        return [id, ''] as const
      }
    }),
  )
  const map: Record<number, string> = { ...exhibitionTitles.value }
  for (const [id, title] of pairs) if (title) map[id] = title
  exhibitionTitles.value = map
}

function exhibitionLabel(id: number): string {
  return exhibitionTitles.value[id] || `展会 #${id}`
}

/** 信息卡：只保留有值的行，顺序固定 */
interface InfoRow {
  key: string
  label: string
  value: string
}
const infoRows = computed<InfoRow[]>(() => {
  const d = detail.value
  if (!d) return []
  const rows: InfoRow[] = []
  const push = (key: string, label: string, value?: string | null) => {
    const text = (value ?? '').toString().trim()
    if (text) rows.push({ key, label, value: text })
  }
  push('industry', '行业', d.industry)
  push('city', '城市', d.city)
  push('country', '国家/地区', d.country)
  push('booth', '展位号', d.booth_no)
  push('expo', '名录展会', d.expo_name)
  push('company_type', '企业类型', d.company_type)
  push('scale', '企业规模', d.scale)
  push('product_count', '名录展品', d.product_count ? `${d.product_count} 件` : '')
  push('source', '数据来源', d.source)
  return rows
})

function formatCount(value?: number | null): string {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return '—'
  return n >= 10000
    ? `${Math.round((n / 10000) * 10) / 10} 万`
    : n.toLocaleString('zh-CN')
}

function markBrokenProduct(id: number): void {
  if (!brokenProductIds.value.includes(id)) brokenProductIds.value.push(id)
}

function productImage(product: { id: number; image?: string | null; category?: string | null }): string {
  // 无图 / 图挂了 → 该品类的几何占位图（与展品库同一套兜底，不出现破图）
  if (brokenProductIds.value.includes(product.id)) return categoryImage(product.category)
  const src = (product.image || '').toString().trim()
  return src || categoryImage(product.category)
}

/** 官网地址做一次协议补全 + 只接受 http(s)，防止 `javascript:` 之类被渲染成可点链接 */
const safeWebsite = computed(() => {
  const raw = website.value
  if (!raw) return ''
  const withScheme = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`
  return /^https?:\/\//i.test(withScheme) ? withScheme : ''
})

async function load(): Promise<void> {
  const id = Number(route.params.id)
  loading.value = true
  failed.value = false
  brokenProductIds.value = []

  if (!Number.isFinite(id) || id <= 0) {
    detail.value = null
    failed.value = true
    loading.value = false
    return
  }

  try {
    const res = await catalogApi.getExhibitor(id)
    detail.value = res
    failed.value = !res
  } catch {
    detail.value = null
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => route.params.id, load)
// detail 加载完成后才知道属于哪些展会：补一次标题
watch(
  exhibitionIds,
  (ids) => {
    if (ids.length) void loadExhibitionTitles(ids)
  },
  { immediate: true },
)
</script>

<template>
  <div class="page">
    <nav class="breadcrumb" aria-label="面包屑">
      <router-link to="/">首页</router-link>
      <span class="sep">/</span>
      <router-link :to="{ name: 'catalog-exhibitors' }">展商名录</router-link>
      <span class="sep">/</span>
      <span class="crumb-current">展商详情</span>
    </nav>

    <div v-if="loading" class="state" aria-busy="true">
      <p class="state-text">正在读取展商资料…</p>
    </div>

    <div v-else-if="failed || !detail" class="state">
      <p class="state-title">没有找到这家展商</p>
      <p class="state-text">该展商可能已从名录移除，或者链接里的编号不正确。</p>
      <div class="state-actions">
        <button type="button" class="primary-btn" @click="load">重试</button>
        <router-link class="ghost-btn" :to="{ name: 'catalog-exhibitors' }">返回名录</router-link>
      </div>
    </div>

    <template v-else>
      <!-- 头部：头像 + 名称 + 英文名 + 官网 -->
      <header class="profile">
        <CompanyAvatar :name="name" :size="76" class="profile-avatar" />
        <div class="profile-main">
          <h1 class="profile-name">{{ name || '未命名展商' }}</h1>
          <p v-if="nameEn" class="profile-name-en">{{ nameEn }}</p>
          <div class="profile-meta">
            <span v-if="detail.industry" class="tag">🏷️ {{ detail.industry }}</span>
            <span v-if="detail.city" class="tag">📍 {{ detail.city }}</span>
            <span v-if="detail.booth_no" class="tag">🔖 展位 {{ detail.booth_no }}</span>
            <span v-if="detail.product_count" class="tag tag-soft">
              📦 {{ formatCount(detail.product_count) }} 件展品
            </span>
          </div>
        </div>
        <div class="profile-actions">
          <a
            v-if="safeWebsite"
            class="primary-btn"
            :href="safeWebsite"
            target="_blank"
            rel="noopener noreferrer"
          >访问官网 ↗</a>
          <router-link class="ghost-btn" :to="{ name: 'catalog-exhibitors' }">返回名录</router-link>
        </div>
      </header>

      <div class="body">
        <!-- 企业介绍 -->
        <section class="intro">
          <h2 class="section-title">企业介绍</h2>
          <p v-if="description" class="intro-text">{{ description }}</p>
          <p v-else class="intro-empty">
            该展商在公开名录里没有提供简介。名录为第三方公开信息快照，缺字段属正常。
          </p>
        </section>

        <!-- 展商信息卡（参考站的「联系方式」卡位置） -->
        <aside class="info-card">
          <h2 class="section-title">展商信息</h2>
          <dl v-if="infoRows.length" class="info-list">
            <div v-for="row in infoRows" :key="row.key" class="info-row">
              <dt class="info-label">{{ row.label }}</dt>
              <dd class="info-value">{{ row.value }}</dd>
            </div>
          </dl>
          <p v-else class="intro-empty">暂无更多资料。</p>

          <div v-if="exhibitionIds.length" class="info-expos">
            <span class="info-label">所属展会</span>
            <div class="expo-links">
              <router-link
                v-for="id in exhibitionIds"
                :key="id"
                class="expo-link"
                :to="`/exhibitions/${id}`"
              >{{ exhibitionLabel(id) }} ›</router-link>
            </div>
          </div>
        </aside>
      </div>

      <!-- 公司产品（参考站「公司产品」网格） -->
      <section class="products">
        <div class="products-head">
          <h2 class="section-title">公司产品</h2>
          <span v-if="products.length" class="products-count">
            名录收录 {{ formatCount(detail.product_count) }} 件，这里展示前 {{ products.length }} 件
          </span>
        </div>

        <div v-if="products.length" class="product-grid">
          <router-link
            v-for="p in products"
            :key="p.id"
            class="product-card"
            :to="{ name: 'catalog-product-detail', params: { id: p.id } }"
          >
            <div class="product-thumb">
              <img
                :src="productImage(p)"
                :alt="p.name"
                loading="lazy"
                @error="markBrokenProduct(p.id)"
              />
            </div>
            <h3 class="product-name" :title="p.name">{{ p.name }}</h3>
            <p v-if="p.category" class="product-cat">{{ p.category }}</p>
          </router-link>
        </div>
        <p v-else class="intro-empty">该展商在名录里没有收录展品。</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-5) var(--space-5) var(--space-8);
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  font-size: var(--font-xs);
  color: var(--ink-500);
}
.breadcrumb a {
  color: var(--ink-500);
  text-decoration: none;
}
.breadcrumb a:hover {
  color: var(--brand-600);
}
.sep {
  color: var(--ink-300);
}
.crumb-current {
  color: var(--ink-700);
}

/* 头部 */
.profile {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}
.profile-avatar {
  flex: none;
}
.profile-main {
  flex: 1 1 auto;
  min-width: 0;
}
.profile-name {
  font-size: var(--font-h3);
  line-height: var(--line-h3);
  font-weight: var(--weight-h3);
  color: var(--ink-900);
}
.profile-name-en {
  margin-top: 2px;
  font-size: var(--font-xs);
  line-height: var(--line-xs);
  color: var(--ink-500);
}
.profile-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-top: var(--space-2);
}
.tag {
  padding: 2px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--brand-50);
  color: var(--brand-600);
  font-size: var(--font-xs);
  line-height: 1.6;
  white-space: nowrap;
}
.tag-soft {
  background: var(--surface-2);
  color: var(--ink-700);
}
.profile-actions {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: stretch;
}

/* 主体两栏 */
.body {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: var(--space-4);
  margin-top: var(--space-4);
}
@media (max-width: 900px) {
  .body {
    grid-template-columns: minmax(0, 1fr);
  }
}

.section-title {
  font-size: var(--font-body);
  line-height: 1.4;
  font-weight: 600;
  color: var(--ink-900);
  margin-bottom: var(--space-3);
}

.intro {
  padding: var(--space-5);
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
}
.intro-text {
  font-size: var(--font-sm);
  line-height: var(--line-body);
  color: var(--ink-700);
  white-space: pre-wrap;
}
.intro-empty {
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: var(--ink-500);
}

.info-card {
  padding: var(--space-5);
  background: var(--brand-50);
  border: 1px solid var(--brand-100);
  border-radius: var(--radius-card);
}
.info-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.info-row {
  display: flex;
  gap: var(--space-2);
  align-items: baseline;
}
.info-label {
  flex: none;
  width: 5.5em;
  color: var(--brand-700);
  font-size: var(--font-xs);
  font-weight: 600;
}
.info-value {
  flex: 1 1 auto;
  min-width: 0;
  font-size: var(--font-sm);
  line-height: var(--line-sm);
  color: var(--ink-700);
  word-break: break-word;
}
.info-expos {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px dashed var(--brand-100);
  display: flex;
  gap: var(--space-2);
  align-items: baseline;
}
.expo-links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.expo-link {
  max-width: 100%;
  font-size: var(--font-xs);
  line-height: 1.5;
  color: var(--brand-600);
  text-decoration: none;
  padding: 2px var(--space-2);
  background: var(--surface-0);
  border: 1px solid var(--brand-100);
  border-radius: var(--radius-full);
  white-space: normal;
  word-break: break-word;
}
.expo-link:hover {
  border-color: var(--brand-500);
}

/* 公司产品 */
.products {
  margin-top: var(--space-5);
}
.products-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.products-head .section-title {
  margin-bottom: 0;
}
.products-count {
  font-size: var(--font-xs);
  color: var(--ink-500);
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}
@media (min-width: 768px) {
  .product-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (min-width: 1200px) {
  .product-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
}

.product-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--surface-0);
  border: 1px solid var(--ink-100);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  color: inherit;
  text-decoration: none;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.product-card:hover {
  transform: translateY(-2px);
  border-color: var(--brand-300);
  box-shadow: var(--shadow-hover);
  color: inherit;
}
.product-thumb {
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: var(--radius-md);
  background: var(--surface-2);
}
.product-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.product-name {
  font-size: var(--font-sm);
  line-height: 1.45;
  font-weight: 600;
  color: var(--ink-900);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: calc(var(--font-sm) * 1.45 * 2);
}
.product-cat {
  font-size: var(--font-xs);
  color: var(--ink-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 按钮 */
.primary-btn,
.ghost-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px var(--space-4);
  border-radius: var(--radius-btn);
  font-size: var(--font-sm);
  font-family: inherit;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: center;
}
.primary-btn {
  border: 1px solid var(--brand-700);
  background: var(--brand-700);
  color: var(--surface-0);
}
.primary-btn:hover {
  background: var(--brand-600);
  border-color: var(--brand-600);
  color: var(--surface-0);
}
.ghost-btn {
  border: 1px solid var(--ink-100);
  background: var(--surface-0);
  color: var(--ink-700);
}
.ghost-btn:hover {
  border-color: var(--brand-500);
  color: var(--brand-600);
}

/* 状态 */
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
  gap: var(--space-3);
  flex-wrap: wrap;
}

@media (max-width: 640px) {
  .page {
    padding: var(--space-4) var(--space-4) var(--space-7);
  }
  .profile {
    flex-wrap: wrap;
  }
  .profile-actions {
    flex-direction: row;
    flex: 1 1 100%;
  }
}
</style>
