<template>
  <div class="container page-wrapper find-page">
    <!-- 页头 -->
    <header class="fp-head">
      <h1>找展</h1>
      <p class="fp-sub">
        不用按数据库字段填表——<strong>一句话说出你的需求</strong>，
        我们拆成筛选条件，拆不出的留白，绝不猜测。
      </p>
    </header>

    <!-- 自然语言输入 -->
    <section class="ask-card">
      <label class="ask-label" for="ask-input">你这样问（自由输入，不强制填表）</label>
      <div class="ask-row">
        <input
          id="ask-input"
          v-model="query"
          class="ask-input"
          type="text"
          placeholder="例如：我要参加 11 月的上海食品展，预算 8 万"
          autocomplete="off"
          @input="onQueryInput"
          @keyup.enter="runParse"
        />
        <button class="btn btn-primary ask-btn" :disabled="parsing || !query.trim()" @click="runParse">
          {{ parsing ? '解析中…' : '找展' }}
        </button>
      </div>
      <p class="ask-hint">输入框只做一件事：把口语留住。下面的识别结果可以点开修改。</p>

      <!-- 识别结果 chips -->
      <div v-if="parsed" class="chips-block">
        <div class="chips-title">
          识别结果
          <span class="chips-count">理解了 {{ parsed.understood }} / {{ parsed.chips.length }} 项</span>
        </div>
        <div class="chips-row">
          <template v-for="c in parsed.chips" :key="c.key">
            <!-- 未提供：置灰，点击给提示 -->
            <button
              v-if="!c.provided"
              class="chip chip-empty"
              :title="`没读出${c.label}——留白，不猜`"
              @click="focusInput"
            >
              {{ c.label }} ＝ 未提供
            </button>
            <!-- 已识别：可点开改、可删 -->
            <span v-else class="chip chip-on">
              <span class="chip-text" @click="startEdit(c)">
                {{ c.label }} ＝ <b>{{ c.display }}</b>
              </span>
              <button class="chip-x" :aria-label="`删除${c.label}`" @click="removeChip(c)">×</button>
            </span>
          </template>
        </div>
        <!-- chip 内联编辑 -->
        <div v-if="editing" class="chip-edit">
          <span class="ce-label">改「{{ editing.label }}」：</span>
          <select
            v-if="editing.options && editing.options.length"
            v-model="editValue"
            class="ce-select"
          >
            <option v-for="o in editing.options" :key="o" :value="o">{{ o }}</option>
          </select>
          <input
            v-else
            v-model="editValue"
            class="ce-input"
            type="text"
            @keyup.enter="confirmEdit"
          />
          <button class="btn btn-sm btn-primary" @click="confirmEdit">改好了</button>
          <button class="btn btn-sm btn-outline" @click="editing = null">取消</button>
        </div>
        <p v-if="parsed.note" class="chips-note">{{ parsed.note }}</p>
      </div>
    </section>

    <!-- 左引导 + 右结果 -->
    <div class="fp-body">
      <!-- 左：五种引导 -->
      <aside class="guide-col">
        <h2 class="guide-title">五种引导，从最省事到最精确</h2>

        <!-- ① 分类选择器 -->
        <section class="guide-item">
          <h3><i>①</i> 分类选择器</h3>
          <p class="gi-desc">选完自动填基线条件</p>
          <div class="gi-form">
            <select v-model="pick.category" class="gi-select" @change="applyPick">
              <option value="">品类（不限）</option>
              <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
            </select>
            <select v-model="pick.city" class="gi-select" @change="applyPick">
              <option value="">城市（不限）</option>
              <option v-for="c in cities" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
        </section>

        <!-- ② 示例 chips -->
        <section class="guide-item">
          <h3><i>②</i> 示例问法</h3>
          <p class="gi-desc">点一条直接填进输入框</p>
          <div class="ex-chips">
            <button
              v-for="ex in examples"
              :key="ex"
              class="ex-chip"
              @click="useExample(ex)"
            >{{ ex }}</button>
          </div>
        </section>

        <!-- ③ 句式模板 -->
        <section class="guide-item">
          <h3><i>③</i> 句式模板</h3>
          <p class="gi-desc">照着填，位置随便放</p>
          <button class="tpl-line" @click="useExample('我要参加 11 月的上海食品展，预算 5 万')">
            我要参加 <em>[月份]</em> 的 <em>[城市][品类]</em> 展，预算 <em>[金额]</em>
          </button>
        </section>

        <!-- ④ 实时回显 -->
        <section class="guide-item">
          <h3><i>④</i> 实时回显</h3>
          <p class="gi-desc">边打字边在下方识别，错了点开改</p>
        </section>

        <!-- ⑤ 结果预览 -->
        <section class="guide-item">
          <h3><i>⑤</i> 结果预览</h3>
          <p class="gi-desc">
            {{ parsed ? `按当前条件命中 ${total} 场` : '先给 3 条示例候选，让人相信「这么问有用」' }}
          </p>
        </section>

        <!-- 判断原则 -->
        <div class="judge-box">
          <b>判断：</b>不追求抽取全对，追求「抽错也能用」。字段缺失一律落为「未提供」，
          绝不猜测、绝不把猜测写成事实。
        </div>
      </aside>

      <!-- 右：结果列表 -->
      <section class="result-col">
        <div class="rc-head">
          <h2>{{ parsed ? '匹配结果' : '示例候选' }}</h2>
          <RouterLink v-if="parsed" class="rc-more" to="/expo-intel">进完整列表 →</RouterLink>
        </div>

        <LoadingSkeleton v-if="loading" :lines="5" />
        <EmptyState
          v-else-if="failed"
          icon="⚠️"
          message="接口没有响应，请确认后端已启动"
        />
        <EmptyState
          v-else-if="items.length === 0"
          icon="🔍"
          message="没有符合条件的展会，试试删掉一个识别条件"
        />

        <article
          v-for="it in items"
          :key="it.slug"
          class="res-card"
          tabindex="0"
          role="link"
          @click="goDetail(it.slug)"
          @keyup.enter="goDetail(it.slug)"
        >
          <div class="rc-id">
            <h3 class="rc-name">
              {{ it.name_cn }}
              <span v-if="it.primary_category" class="rc-cat">{{ it.primary_category }}</span>
            </h3>
            <p class="rc-meta">
              {{ it.city || '城市未知' }}
              <template v-if="it.venue_name"> · {{ it.venue_name }}</template>
              · {{ fmtDateRange(it.start_date, it.end_date) }}
            </p>
          </div>

          <div class="rc-nums">
            <div class="rcn">
              <span class="rcn-k">观众</span>
              <span class="rcn-v">
                <em v-if="it.visitor_origin === 'estimated'" class="est-tag" :title="estTitle(it, 'visitor_count')">≈估</em>
                {{ fmtCount(it.visitor_count) }}
              </span>
            </div>
            <div class="rcn">
              <span class="rcn-k">展商</span>
              <span class="rcn-v">
                <em v-if="it.exhibitor_origin === 'estimated'" class="est-tag" :title="estTitle(it, 'exhibitor_count')">≈估</em>
                {{ fmtCount(it.exhibitor_count) }}
              </span>
            </div>
            <div class="rcn">
              <span class="rcn-k">面积</span>
              <span class="rcn-v">
                <em v-if="it.area_origin === 'estimated'" class="est-tag" :title="estTitle(it, 'exhibit_area_sqm')">≈估</em>
                {{ it.exhibit_area_sqm ? fmtCount(it.exhibit_area_sqm) + '㎡' : '—' }}
              </span>
            </div>
          </div>

          <div class="rc-verdict">
            <BandBadge
              :band="it.e1.band"
              :label="it.e1.label"
              :hint="it.e1.hint"
              :tone="e1Tone(it.e1.band)"
              :value="it.e1.ratio !== null ? fmtRatio(it.e1.ratio) : null"
              prefix="客群"
              size="sm"
            />
            <span
              v-if="it.e1.ratio_origin === 'estimated'"
              class="ratio-est"
              title="比值用到了估算输入，不是纯实测"
            >含估算</span>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import BandBadge from '@/components/persona/BandBadge.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import {
  e1Tone,
  fmtCount,
  fmtDateRange,
  fmtRatio,
  personaApi,
  type ExpoPersonaItem,
  type ParseChip,
  type ParseQueryResult,
} from '@/api/persona'

const router = useRouter()

// ---- 输入与解析 ----
const query = ref('')
const parsing = ref(false)
const parsed = ref<ParseQueryResult | null>(null)
const failed = ref(false)

// ---- 结果 ----
const items = ref<ExpoPersonaItem[]>([])
const total = ref(0)
const loading = ref(false)

// ---- 编辑 chip ----
const editing = ref<ParseChip | null>(null)
const editValue = ref('')

// ---- 分类选择器 ----
const pick = ref({ category: '', city: '' })
const categories = ref<string[]>([])
const cities = ref<string[]>([])

// 示例问法必须挑库里真有结果的——第一条就 0 条，用户会认为"这么问没用"。
// 每条都对 /persona/expos 实测过命中数（2026-11-04）。
const examples = [
  '11 月上海的食品展',
  '广州的食品展有哪些',
  '深圳的科技展',
  '下半年的大型机械展',
  '12 月深圳的物流展',
]

let debounceTimer: ReturnType<typeof setTimeout> | undefined

function onQueryInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(runParse, 600) // 边打字边识别（引导④）
}

async function runParse() {
  const text = query.value.trim()
  if (!text) return
  parsing.value = true
  try {
    const res = await personaApi.parseQuery(text)
    parsed.value = res
    editing.value = null
    await fetchResults(res.filters)
  } catch {
    failed.value = true
  } finally {
    parsing.value = false
  }
}

/** 手动改过 chip 后，把 chips 状态还原成 filters 再查 */
function chipsToFilters(): ParseQueryResult['filters'] {
  const f: ParseQueryResult['filters'] = {}
  if (!parsed.value) return f
  for (const c of parsed.value.chips) {
    if (!c.provided) continue
    if (c.key === 'category') f.category = String(c.value)
    if (c.key === 'city') f.city = String(c.value)
    if (c.key === 'month') {
      const v = c.value as number | { from: number; to: number }
      if (typeof v === 'number') {
        f.month_from = v
        f.month_to = v
      } else if (v && typeof v === 'object') {
        f.month_from = v.from
        f.month_to = v.to
      }
    }
  }
  return f
}

async function fetchResults(filters: ParseQueryResult['filters']) {
  loading.value = true
  try {
    const res = await personaApi.getExpos({
      ...filters,
      page: 1,
      page_size: 10,
      sort: 'start_date',
      order: 'asc',
    })
    items.value = res.items
    total.value = res.pagination.total
    failed.value = false
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

function startEdit(c: ParseChip) {
  editing.value = c
  editValue.value = String(c.value ?? '')
}

function confirmEdit() {
  if (!editing.value || !parsed.value) return
  const chip = parsed.value.chips.find((x) => x.key === editing.value!.key)
  if (chip) {
    chip.provided = true
    chip.value = editValue.value
    chip.display = editValue.value
    chip.evidence = '手动修改'
  }
  // 预算/规模不参与筛选（无价格、规模语义模糊），改了也只改显示
  parsed.value.understood = parsed.value.chips.filter((x) => x.provided).length
  editing.value = null
  fetchResults(chipsToFilters())
}

function removeChip(c: ParseChip) {
  if (!parsed.value) return
  const chip = parsed.value.chips.find((x) => x.key === c.key)
  if (chip) {
    chip.provided = false
    chip.value = null
    chip.display = '未提供'
    chip.evidence = null
  }
  parsed.value.understood = parsed.value.chips.filter((x) => x.provided).length
  editing.value = null
  fetchResults(chipsToFilters())
}

function focusInput() {
  document.getElementById('ask-input')?.focus()
}

function useExample(text: string) {
  query.value = text
  runParse()
}

function applyPick() {
  // 选分类/城市 → 拼进输入框再走同一条解析链路，保持"识别结果可见可改"
  const parts: string[] = []
  if (pick.value.city) parts.push(pick.value.city)
  if (pick.value.category) parts.push(pick.value.category + '展')
  if (parts.length) {
    query.value = parts.join('的')
    runParse()
  } else if (parsed.value) {
    fetchResults({})
  }
}

function estTitle(it: ExpoPersonaItem, field: string): string {
  const e = it.estimates?.[field]
  if (!e) return '估算值'
  return `估算 ≈${e.value.toLocaleString('zh-CN')}（区间 ${e.lo.toLocaleString('zh-CN')}~${e.hi.toLocaleString('zh-CN')}）\n证据：${e.evidence.map((x) => x.basis).join('；')}`
}

function goDetail(slug: string) {
  router.push({ name: 'expo-intel-detail', params: { slug } })
}

onMounted(async () => {
  // 分类/城市选项来自 overview（后端口径），示例候选先给 3 条
  try {
    const ov = await personaApi.getOverview()
    categories.value = (ov.categories || []).map((x) => x.category).filter((x) => x !== '未分类')
  } catch { /* 选项缺失不阻断主流程 */ }
  try {
    const res = await personaApi.getExpos({ page: 1, page_size: 3, sort: 'start_date', order: 'asc' })
    items.value = res.items
    total.value = res.pagination.total
  } catch {
    failed.value = true
  }
})
</script>

<style scoped>
.find-page {
  padding-top: var(--spacing-lg);
  padding-bottom: var(--spacing-xl);
}

/* ---- 页头 ---- */
.fp-head h1 {
  margin: 0 0 6px;
  font-size: var(--font-h2);
  font-weight: var(--weight-h2);
  color: var(--ink-900);
  letter-spacing: -0.02em;
}
.fp-sub {
  margin: 0 0 var(--spacing-md);
  color: var(--ink-500);
  font-size: 14px;
}
.fp-sub strong {
  color: var(--ink-700);
}

/* ---- 输入卡 ---- */
.ask-card {
  background: var(--ink-50, #fafafa);
  border: 1px solid var(--border-100, #e8e8e8);
  border-radius: var(--radius-lg, 12px);
  padding: 18px 20px;
  margin-bottom: var(--spacing-lg);
}
.ask-label {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-700);
  margin-bottom: 8px;
}
.ask-row {
  display: flex;
  gap: 10px;
}
@media (max-width: 640px) {
  .ask-row {
    flex-wrap: wrap;
  }
  .ask-input {
    min-width: 0;
  }
}
.ask-input {
  flex: 1;
  height: 44px;
  padding: 0 14px;
  font-size: 15px;
  border: 1.5px solid var(--brand-400, #b7c9f2);
  border-radius: var(--radius-md, 8px);
  background: #fff;
  color: var(--ink-900);
  outline: none;
  transition: border-color 0.15s;
}
.ask-input:focus {
  border-color: var(--brand-500, #4a6cf7);
}
.ask-btn {
  height: 44px;
  padding: 0 22px;
  white-space: nowrap;
}
.ask-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--ink-400, #999);
}

/* ---- chips ---- */
.chips-block {
  margin-top: 14px;
  border-top: 1px dashed var(--border-100, #e0e0e0);
  padding-top: 12px;
}
.chips-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--brand-700, #2c4bb8);
  margin-bottom: 8px;
}
.chips-count {
  margin-left: 8px;
  font-weight: 400;
  font-size: 12px;
  color: var(--ink-400, #999);
}
.chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: filter 0.12s;
}
.chip:hover {
  filter: brightness(0.96);
}
.chip-on {
  background: var(--brand-600, #3b5bdb);
  color: #fff;
}
.chip-on b {
  font-weight: 700;
}
.chip-text {
  cursor: pointer;
}
.chip-x {
  background: transparent;
  border: 0;
  color: rgba(255, 255, 255, 0.8);
  font-size: 15px;
  line-height: 1;
  padding: 0 2px;
  cursor: pointer;
}
.chip-x:hover {
  color: #fff;
}
.chip-empty {
  background: var(--ink-100, #eee);
  color: var(--ink-400, #999);
  border: 1px dashed var(--border-200, #ccc);
  cursor: pointer;
}
.chip-edit {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.ce-label {
  font-size: 12.5px;
  color: var(--ink-600, #666);
}
.ce-select,
.ce-input {
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--border-200, #ccc);
  border-radius: 6px;
  font-size: 13px;
  min-width: 160px;
}
.chips-note {
  margin: 10px 0 0;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--ink-400, #999);
}

/* ---- 左右布局 ---- */
.fp-body {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: var(--spacing-lg);
  align-items: start;
}
/* min-width:0 不能省——grid 子项默认 min-content 撑开，
   390px 下右栏长词会把整列顶宽造成横向溢出（实测 446px）。 */
.guide-col,
.result-col {
  min-width: 0;
}
@media (max-width: 900px) {
  .fp-body {
    grid-template-columns: minmax(0, 1fr);
  }
  .guide-col {
    position: static;
  }
}

/* ---- 左栏 ---- */
.guide-col {
  position: sticky;
  top: 80px;
}
.guide-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-800, #333);
}
.guide-item {
  margin-bottom: 16px;
}
.guide-item h3 {
  margin: 0 0 3px;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-700, #444);
}
.guide-item h3 i {
  font-style: normal;
  color: var(--brand-500, #4a6cf7);
  margin-right: 4px;
}
.gi-desc {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--ink-400, #999);
}
.gi-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.gi-select {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--border-200, #ccc);
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
}
.ex-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ex-chip {
  padding: 5px 10px;
  font-size: 12px;
  background: #fff;
  border: 1px solid var(--border-200, #ccc);
  border-radius: 14px;
  color: var(--ink-600, #666);
  cursor: pointer;
  transition: all 0.12s;
}
.ex-chip:hover {
  border-color: var(--brand-400, #b7c9f2);
  color: var(--brand-600, #3b5bdb);
}
.tpl-line {
  display: block;
  width: 100%;
  text-align: left;
  padding: 10px 12px;
  font-size: 12.5px;
  line-height: 1.7;
  background: var(--brand-50, #f0f4ff);
  border: 1px solid var(--brand-100, #dde6ff);
  border-radius: 8px;
  color: var(--ink-600, #666);
  cursor: pointer;
}
.tpl-line em {
  font-style: normal;
  color: var(--brand-600, #3b5bdb);
  font-weight: 700;
}
.judge-box {
  margin-top: 18px;
  padding: 12px 14px;
  background: #fffbeb;
  border: 1px solid #f5e2b5;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.7;
  color: #6b5316;
}

/* ---- 右栏 ---- */
.rc-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}
.rc-head h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: var(--ink-800, #333);
}
.rc-more {
  font-size: 12.5px;
  color: var(--brand-600, #3b5bdb);
  text-decoration: none;
}
.rc-more:hover {
  text-decoration: underline;
}

.res-card {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid var(--border-100, #e8e8e8);
  border-radius: 10px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: border-color 0.12s, box-shadow 0.12s;
}
.res-card:hover {
  border-color: var(--brand-300, #c9d6f7);
  box-shadow: 0 2px 8px rgba(59, 91, 219, 0.08);
}
.rc-name {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-900);
}
.rc-cat {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 400;
  color: var(--brand-600, #3b5bdb);
  background: var(--brand-50, #f0f4ff);
  border-radius: 10px;
  vertical-align: 2px;
}
.rc-meta {
  margin: 0;
  font-size: 12.5px;
  color: var(--ink-500, #888);
}

.rc-nums {
  display: flex;
  gap: 16px;
}
.rcn {
  text-align: center;
  min-width: 64px;
}
.rcn-k {
  display: block;
  font-size: 11px;
  color: var(--ink-400, #999);
  margin-bottom: 2px;
}
.rcn-v {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-800, #333);
  font-variant-numeric: tabular-nums;
}
.est-tag {
  display: inline-block;
  margin-right: 3px;
  padding: 1px 5px;
  font-size: 10px;
  font-style: normal;
  font-weight: 700;
  color: #b45309;
  background: #fef3c7;
  border-radius: 8px;
  cursor: help;
}

.rc-verdict {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
@media (max-width: 640px) {
  .res-card {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .rc-nums {
    justify-content: flex-start;
  }
  .rc-verdict {
    align-items: flex-start;
    flex-direction: row;
  }
}
.ratio-est {
  font-size: 10px;
  color: #b45309;
  background: #fef3c7;
  padding: 1px 6px;
  border-radius: 8px;
}
</style>
