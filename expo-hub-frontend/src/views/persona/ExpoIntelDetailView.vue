<script setup lang="ts">
/**
 * 展会评估 · 详情页
 *
 * 这一页的职责不是"展示更多信息"，是**回答"为什么是这个结论"**。
 * 所以每个结论都跟着三样东西：
 *   1) 原始数（观众/展商/面积到底是几）
 *   2) 口径（人数还是人次、建筑面积还是净面积）
 *   3) 来源（官网一手 / 第三方平台）
 *
 * 缺一样，用户就只能把结论当成结论，而不能自己判断它值不值得信。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BandBadge from '@/components/persona/BandBadge.vue'
import E5Checklist from '@/components/persona/E5Checklist.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import {
  caliberLabel,
  e1Tone,
  e4Tone,
  fmtCount,
  fmtDateRange,
  fmtRatio,
  personaApi,
  type ExpoPersonaDetail,
} from '@/api/persona'

const route = useRoute()
const router = useRouter()

const data = ref<ExpoPersonaDetail | null>(null)
const loading = ref(true)
const notFound = ref(false)
const failed = ref(false)

const slug = computed(() => String(route.params.slug || ''))

async function fetchDetail() {
  loading.value = true
  notFound.value = false
  failed.value = false
  try {
    data.value = await personaApi.getExpo(slug.value)
  } catch (e: any) {
    if (e?.response?.status === 404) notFound.value = true
    else failed.value = true
    data.value = null
  } finally {
    loading.value = false
  }
}

onMounted(fetchDetail)
watch(slug, fetchDetail)

function goBack() {
  router.push({ name: 'expo-intel' })
}

const d = computed(() => data.value)

/** E1 缺哪一个数——直接指出来，而不是笼统说"数据不足" */
const e1Missing = computed(() => {
  if (!d.value) return ''
  const miss: string[] = []
  if (!d.value.visitor_count) miss.push('观众数')
  if (!d.value.exhibitor_count) miss.push('展商数')
  if (miss.length === 0) return ''
  if (miss.length === 2) return '观众数和展商数都没有'
  return `缺${miss[0]}`
})

const e1Basis = computed(() => {
  const note = d.value?.note || ''
  if (note.includes('ratio_basis=person')) return '页面直接报人数，比值可信'
  if (note.includes('ratio_basis=converted_from_visit')) {
    return '页面报的是「人次」，已按 ÷2 折算成人数——这是行业经验系数，不是实测'
  }
  return ''
})

const isThirdParty = computed(() => d.value?.scale_source === 'qufair')

/**
 * 只显示**词表内的**枚举值。
 * 数据里出现过 `biz_type = "mixed"` 这种串行（mixed 是 audience_access 的取值），
 * 原样渲染会在页面上出现一个孤零零的英文单词。认不出的值宁可不显示——
 * 少一个标签不影响判断，显示一个错标签会让人怀疑整页数据。
 */
const ACCESS_LABEL: Record<string, string> = {
  trade_only: '仅专业观众',
  public: '对公众开放',
  mixed: '专业+公众',
}
const BIZ_LABEL: Record<string, string> = {
  b2b: 'B2B',
  b2c: 'B2C',
  b2b2c: 'B2B2C',
}

const accessLabel = computed(() => {
  const v = (d.value?.audience_access || '').toLowerCase()
  return ACCESS_LABEL[v] || ''
})

const bizLabel = computed(() => {
  const v = (d.value?.biz_type || '').toLowerCase()
  return BIZ_LABEL[v] || ''
})

const CALIBER_NOTE: Record<string, string> = {
  person: '人数',
  visit: '人次',
  company: '企业数（非展位数）',
  booth: '展位数',
  gross: '建筑面积（含通道与服务区）',
  net: '净面积',
}

function caliberText(c: string | null): string {
  if (!c) return '口径未标注'
  return CALIBER_NOTE[c] ?? caliberLabel(c)
}

const sourceBody = computed(() =>
  // 后端有的 label 自带「来源未标注」前缀，有的不带（如第三方源那句），
  // 统一剥掉再拼，否则会渲染成「来源：来源未标注」
  (d.value?.scale_source_label || '').replace(/^来源[：:]?\s*/, ''),
)

/** 观测溯源的中文名 */
const SOURCE_NAME: Record<string, string> = {
  web: '官网/公开网页',
  thirdparty: '第三方会展平台',
  manual: '人工录入',
  csv: '批量导入',
}

const daysTone = computed(() => {
  const n = d.value?.e4.days_left
  if (n === null || n === undefined) return 'muted'
  if (n < 0) return 'muted'
  if (n <= 3) return 'bad'
  if (n <= 15) return 'warn'
  return 'good'
})
</script>

<template>
  <div class="container page-wrapper detail-page">
    <button class="back-link" @click="goBack">← 返回展会评估</button>

    <LoadingSkeleton v-if="loading" :lines="10" />

    <div v-else-if="notFound" class="notfound">
      <h2>没有这个展会</h2>
      <p>画像库里找不到标识为 <code>{{ slug }}</code> 的展。</p>
      <button class="btn btn-sm btn-outline" @click="goBack">回到列表</button>
    </div>

    <div v-else-if="failed" class="notfound">
      <h2>接口没有响应</h2>
      <p>请确认后端服务已启动（默认 8002 端口）。</p>
    </div>

    <template v-else-if="d">
      <!-- ============ 头部 ============ -->
      <header class="d-head">
        <div class="dh-top">
          <div class="dh-title-wrap">
            <h1>{{ d.name_cn }}</h1>
            <div class="dh-tags">
              <span v-if="d.primary_category" class="dh-tag cat">{{ d.primary_category }}</span>
              <span v-if="d.edition_no" class="dh-tag">第 {{ d.edition_no }} 届</span>
              <span v-if="bizLabel" class="dh-tag">{{ bizLabel }}</span>
              <span v-if="accessLabel" class="dh-tag">{{ accessLabel }}</span>
            </div>
          </div>
        </div>

        <div class="dh-meta">
          <span class="dhm-item"><i>城市</i>{{ d.city || '未知' }}</span>
          <span class="dhm-item"><i>展馆</i>{{ d.venue_name || '未知' }}</span>
          <span class="dhm-item"><i>展期</i>{{ fmtDateRange(d.start_date, d.end_date) }}</span>
        </div>

        <div class="dh-verdicts">
          <BandBadge
            :band="d.e1.band"
            :label="d.e1.label"
            :hint="d.e1.hint"
            :tone="e1Tone(d.e1.band)"
            :value="d.e1.ratio !== null ? fmtRatio(d.e1.ratio) : null"
            prefix="客群可得性"
          />
          <BandBadge
            :band="d.e4.band"
            :label="d.e4.label"
            :hint="d.e4.hint"
            :tone="e4Tone(d.e4.band)"
            prefix="展位可得性"
          />
        </div>
      </header>

      <!-- ============ 两块结论 ============ -->
      <section class="verdict-grid">
        <!-- E1 -->
        <article class="vcard">
          <div class="vc-head">
            <span class="vc-tag">E1 · 客群可得性</span>
            <span class="vc-sub">观众数 ÷ 展商数</span>
          </div>

          <template v-if="d.e1.ratio !== null">
            <div class="vc-big">
              <span class="vcb-num">{{ fmtRatio(d.e1.ratio) }}</span>
              <span class="vcb-unit">个观众 / 展位</span>
            </div>
            <p class="vc-hint">{{ d.e1.hint }}</p>
            <p v-if="e1Basis" class="vc-basis">{{ e1Basis }}</p>
          </template>

          <template v-else>
            <div class="vc-big muted">
              <span class="vcb-num">算不出</span>
            </div>
            <p class="vc-hint">{{ d.e1.hint }}</p>
            <p class="vc-basis">本展{{ e1Missing }}，两个数不齐就除不出比值。</p>
          </template>

          <!-- 目标客群估算：明确标注是假设推导 -->
          <div v-if="d.e1.target_mid" class="vc-target">
            <div class="vct-head">
              <span>其中专业观众估算</span>
              <span class="vct-warn" title="角色命中率 role_hit 目前是人工假设，尚未标定">未标定的估算</span>
            </div>
            <div class="vct-bars">
              <div class="vct-bar">
                <span class="vctb-k">区间</span>
                <span class="vctb-v">{{ fmtCount(d.e1.target_lo) }} — {{ fmtCount(d.e1.target_hi) }}</span>
              </div>
              <div class="vct-bar">
                <span class="vctb-k">中位</span>
                <span class="vctb-v strong">{{ fmtCount(d.e1.target_mid) }}</span>
              </div>
            </div>
          </div>
        </article>

        <!-- E4 -->
        <article class="vcard">
          <div class="vc-head">
            <span class="vc-tag">E4 · 展位可得性</span>
            <span class="vc-sub">距开展日</span>
          </div>

          <div class="vc-big" :class="daysTone">
            <template v-if="d.e4.days_left !== null && d.e4.days_left >= 0">
              <span class="vcb-num">{{ d.e4.days_left }}</span>
              <span class="vcb-unit">天后开展</span>
            </template>
            <template v-else-if="d.e4.band === 'ongoing'">
              <span class="vcb-num">进行中</span>
              <span class="vcb-unit">已开展 {{ Math.abs(d.e4.days_left || 0) }} 天</span>
            </template>
            <template v-else-if="d.e4.days_left !== null">
              <span class="vcb-num">{{ Math.abs(d.e4.days_left) }}</span>
              <span class="vcb-unit">天前已闭幕</span>
            </template>
            <template v-else>
              <span class="vcb-num">未知</span>
              <span class="vcb-unit">无开展日期</span>
            </template>
          </div>

          <p class="vc-hint">{{ d.e4.hint }}</p>

          <div class="vc-extra">
            <span class="vce-k">展期</span>
            <span class="vce-v">{{ fmtDateRange(d.start_date, d.end_date) }}</span>
          </div>
          <div v-if="d.booth_deadline" class="vc-extra">
            <span class="vce-k">展位截止</span>
            <span class="vce-v">{{ d.booth_deadline }}</span>
          </div>
          <div v-else class="vc-extra muted">
            <span class="vce-k">展位截止</span>
            <span class="vce-v">主办方未公开，按开展日估算</span>
          </div>
        </article>
      </section>

      <!-- ============ 数据明细 ============ -->
      <section class="detail-card">
        <div class="dc-head">
          <h2>规模数据与来源</h2>
          <span v-if="isThirdParty" class="dc-warn">第三方源</span>
        </div>

        <div class="dc-table">
          <div class="dct-row dct-head">
            <span>指标</span><span>数值</span><span>口径</span><span>备注</span>
          </div>
          <div class="dct-row">
            <span class="dct-k">观众数</span>
            <span class="dct-v" :class="{ miss: !d.visitor_count }">{{ fmtCount(d.visitor_count) }}</span>
            <span class="dct-c">{{ caliberText(d.visitor_caliber) }}</span>
            <span class="dct-n">{{ d.visitor_count ? '' : '未采到' }}</span>
          </div>
          <div class="dct-row">
            <span class="dct-k">展商数</span>
            <span class="dct-v" :class="{ miss: !d.exhibitor_count }">{{ fmtCount(d.exhibitor_count) }}</span>
            <span class="dct-c">{{ caliberText(d.exhibitor_caliber) }}</span>
            <span class="dct-n">{{ d.exhibitor_count ? '' : '未采到' }}</span>
          </div>
          <div class="dct-row">
            <span class="dct-k">展览面积</span>
            <span class="dct-v" :class="{ miss: !d.exhibit_area_sqm }">
              {{ d.exhibit_area_sqm ? fmtCount(d.exhibit_area_sqm) + ' ㎡' : '—' }}
            </span>
            <span class="dct-c">{{ caliberText(d.area_caliber) }}</span>
            <span class="dct-n">{{ d.exhibit_area_sqm ? '' : '未采到' }}</span>
          </div>
        </div>

        <p v-if="sourceBody" class="dc-source" :class="{ warn: isThirdParty }">
          <strong>来源：</strong>{{ sourceBody }}
        </p>

        <!-- 观测溯源 -->
        <div v-if="d.observations?.length" class="dc-obs">
          <span class="dco-k">数据来自</span>
          <span v-for="o in d.observations" :key="o.source_type" class="dco-chip">
            {{ SOURCE_NAME[o.source_type] || o.source_type }}
            <b>{{ o.count }}</b>
            <i>条</i>
          </span>
        </div>
      </section>

      <!-- ============ 结论是怎么算出来的 ============ -->
      <section class="detail-card">
        <div class="dc-head">
          <h2>这份结论的依据</h2>
          <span class="dc-sub">版本 {{ d.params_version || d.calibration?.version || '—' }}</span>
        </div>

        <div class="calc-grid">
          <div class="cg-item">
            <span class="cg-k">标定样本</span>
            <span class="cg-v">n = {{ d.calibration?.n ?? '—' }} 个可算比值的展</span>
          </div>
          <div class="cg-item">
            <span class="cg-k">分位线</span>
            <span class="cg-v">
              <template v-if="d.calibration?.p25 !== undefined">
                P25 {{ d.calibration.p25 }} / P50 {{ d.calibration.p50 }} / P75 {{ d.calibration.p75 }}
              </template>
              <template v-else>未提供</template>
            </span>
          </div>
          <div class="cg-item">
            <span class="cg-k">数据完整度</span>
            <span class="cg-v">{{ d.data_status === 'full' ? '三项规模数据齐全'
              : d.data_status === 'partial' ? '部分字段缺失' : '仅有骨架信息' }}</span>
          </div>
          <div class="cg-item">
            <span class="cg-k">计算时间</span>
            <span class="cg-v">{{ (d.computed_at || '').replace('T', ' ') || '—' }}</span>
          </div>
        </div>

        <p v-if="d.calibration?.basis" class="dc-basis">{{ d.calibration.basis }}</p>
        <!-- 样本的已知偏差：只在**本展数据来自第三方源**时展示。
             这条 caveat 讲的是"8 个第三方源条目偏低"，挂在官网数据的展上
             会让人误以为这个展的数也来自第三方。 -->
        <p v-if="isThirdParty && d.calibration?.caveat" class="dc-caveat">{{ d.calibration.caveat }}</p>

        <details v-if="d.note" class="dc-raw">
          <summary>查看计算备注（原始）</summary>
          <pre>{{ d.note }}</pre>
        </details>
      </section>

      <!-- ============ E5 ============ -->
      <E5Checklist :slug="d.slug" />
    </template>
  </div>
</template>

<style scoped>
.detail-page {
  padding-top: var(--spacing-md);
  padding-bottom: var(--spacing-xl);
  max-width: 1000px;
}
.back-link {
  border: none;
  background: transparent;
  color: var(--ink-500);
  font-size: 13px;
  cursor: pointer;
  padding: 4px 0;
  margin-bottom: 8px;
}
.back-link:hover {
  color: var(--brand-600);
}
.notfound {
  padding: 60px 0;
  text-align: center;
  color: var(--ink-500);
}
.notfound h2 {
  font-size: 18px;
  color: var(--ink-900);
  margin: 0 0 8px;
}
.notfound code {
  background: var(--surface-2);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-size: 12px;
}

/* ---------- 头部 ---------- */
.d-head {
  background: var(--surface-0);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
  margin-bottom: var(--spacing-md);
}
.dh-title-wrap h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--ink-900);
  line-height: 1.35;
}
.dh-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.dh-tag {
  font-size: 11px;
  color: var(--ink-500);
  background: var(--surface-1);
  border-radius: var(--radius-sm);
  padding: 2px 7px;
}
.dh-tag.cat {
  color: var(--brand-600);
  background: var(--brand-50);
}
.dh-meta {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  margin: 14px 0;
  padding: 12px 0;
  border-top: 1px solid var(--surface-2);
  border-bottom: 1px solid var(--surface-2);
}
.dhm-item {
  font-size: 13px;
  color: var(--ink-700);
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}
.dhm-item i {
  font-style: normal;
  font-size: 11px;
  color: var(--ink-300);
}
.dh-verdicts {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

/* ---------- 结论卡 ---------- */
.verdict-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}
.vcard {
  background: var(--surface-0);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
}
.vc-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 12px;
}
.vc-tag {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--ink-900);
}
.vc-sub {
  font-size: 11px;
  color: var(--ink-300);
}
.vc-big {
  display: flex;
  align-items: baseline;
  gap: 8px;
  color: var(--brand-700);
}
.vc-big.muted {
  color: var(--ink-300);
}
.vc-big.good { color: #0f7b52; }
.vc-big.warn { color: #96620b; }
.vc-big.bad { color: #a52a1f; }
.vcb-num {
  font-size: 34px;
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
}
.vcb-unit {
  font-size: 12px;
  color: var(--ink-500);
}
.vc-hint {
  margin: 10px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-500);
}
.vc-basis {
  margin: 6px 0 0;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--ink-300);
}
.vc-target {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-color);
}
.vct-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11.5px;
  color: var(--ink-500);
}
.vct-warn {
  font-size: 10px;
  color: #96620b;
  background: #fdf3e0;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  cursor: help;
}
.vct-bars {
  display: flex;
  gap: 18px;
  margin-top: 7px;
}
.vct-bar {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.vctb-k {
  font-size: 10px;
  color: var(--ink-300);
}
.vctb-v {
  font-size: 13px;
  color: var(--ink-700);
  font-variant-numeric: tabular-nums;
}
.vctb-v.strong {
  font-weight: 700;
  color: var(--brand-700);
}
.vc-extra {
  display: flex;
  gap: 8px;
  margin-top: 7px;
  font-size: 12px;
}
/* 只在第一行上方画分隔线：两行都画会变成两条虚线 */
.vc-extra:first-of-type {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-color);
}
.vce-k {
  color: var(--ink-300);
  flex-shrink: 0;
}
.vce-v {
  color: var(--ink-700);
}
.vc-extra.muted .vce-v {
  color: var(--ink-500);
}

/* ---------- 通用卡片 ---------- */
.detail-card {
  background: var(--surface-0);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  margin-bottom: var(--spacing-md);
}
.dc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.dc-head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-900);
}
.dc-sub {
  font-size: 11px;
  color: var(--ink-300);
}
.dc-warn {
  font-size: 10.5px;
  color: #96620b;
  background: #fdf3e0;
  border: 1px solid #f2dcb2;
  border-radius: var(--radius-sm);
  padding: 1px 7px;
}

/* 表格 */
.dc-table {
  border: 1px solid var(--surface-2);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.dct-row {
  display: grid;
  grid-template-columns: 100px 120px minmax(0, 1fr) 80px;
  gap: 10px;
  padding: 9px 12px;
  font-size: 12.5px;
  border-bottom: 1px solid var(--surface-2);
  align-items: baseline;
}
.dct-row:last-child {
  border-bottom: none;
}
.dct-head {
  background: var(--surface-1);
  font-size: 11px;
  color: var(--ink-500);
  font-weight: 600;
}
.dct-k {
  color: var(--ink-500);
}
.dct-v {
  font-weight: 700;
  color: var(--ink-900);
  font-variant-numeric: tabular-nums;
}
.dct-v.miss {
  color: var(--ink-300);
  font-weight: 400;
}
.dct-c {
  color: var(--ink-500);
  font-size: 11.5px;
}
.dct-n {
  color: var(--ink-300);
  font-size: 11px;
  text-align: right;
}

.dc-source {
  margin: 10px 0 0;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--ink-500);
  background: var(--surface-1);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
}
.dc-source.warn {
  background: #fffbeb;
  color: #6b5316;
}
.dc-source strong {
  color: var(--ink-700);
}
.dc-source.warn strong {
  color: #513d0c;
}

.dc-obs {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.dco-k {
  font-size: 11px;
  color: var(--ink-300);
}
.dco-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--ink-700);
  background: var(--surface-1);
  border-radius: var(--radius-sm);
  padding: 2px 7px;
}
.dco-chip b {
  color: var(--brand-600);
  font-variant-numeric: tabular-nums;
}
.dco-chip i {
  font-style: normal;
  color: var(--ink-300);
  font-size: 10px;
}

/* 依据 */
.calc-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 20px;
}
.cg-item {
  display: flex;
  gap: 8px;
  font-size: 12.5px;
  align-items: baseline;
}
.cg-k {
  color: var(--ink-300);
  min-width: 62px;
  flex-shrink: 0;
  font-size: 11.5px;
}
.cg-v {
  color: var(--ink-700);
  font-variant-numeric: tabular-nums;
}
.dc-basis {
  margin: 12px 0 0;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--ink-500);
}
.dc-caveat {
  margin: 8px 0 0;
  font-size: 11.5px;
  line-height: 1.7;
  color: #6b5316;
  background: #fffbeb;
  border-left: 2px solid var(--accent-500);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  padding: 7px 10px;
}
.dc-raw {
  margin-top: 10px;
  font-size: 11.5px;
  color: var(--ink-500);
}
.dc-raw summary {
  cursor: pointer;
  color: var(--brand-600);
}
.dc-raw pre {
  margin: 8px 0 0;
  background: var(--surface-1);
  border-radius: var(--radius-sm);
  padding: 10px;
  font-size: 11px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--ink-700);
}

@media (max-width: 720px) {
  .verdict-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .calc-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .dct-row {
    grid-template-columns: 76px 90px minmax(0, 1fr);
  }
  .dct-n {
    display: none;
  }
  .dct-head span:last-child {
    display: none;
  }
}
</style>
