<script setup lang="ts">
/**
 * E5 交付可行性 · 用户自评清单（内嵌在展会详情页）
 *
 * 这一项和 E1/E4 完全不同：层高、承重、货运通道、供电、消防、吊点
 * 这些数主办方不公开，我们永远抓不到。所以它不"算"，它"问"。
 *
 * 两个刻意的实现决定：
 *
 * 1) **判定永远由后端做**。前端只收集 ok/short/na，结论走 POST /e5/evaluate。
 *    本地再实现一遍加权/优先级，两边迟早会不一致，而用户在页面上看到的是
 *    前端那一份——等于后端做的所有防滥用护栏（na 只放行五项、blocked 压过
 *    incomplete）全部失效。
 *
 * 2) **答案存本地，不落库**。"我的设备多高、我要多少电"是这一次参展的条件，
 *    不是展会属性。存进展会表会让下一个人看到别人的答案并当成事实。
 */
import { computed, onMounted, ref, watch } from 'vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import {
  personaApi,
  type E5Checklist as E5ChecklistData,
  type E5State,
  type E5Verdict,
} from '@/api/persona'

const props = defineProps<{ slug: string }>()

const checklist = ref<E5ChecklistData | null>(null)
const verdict = ref<E5Verdict | null>(null)
const loading = ref(true)
const evaluating = ref(false)
const failed = ref(false)
const expanded = ref(false)

/** 答案按展存在本地 */
const STORAGE_KEY = computed(() => `expo-intel:e5:${props.slug}`)

const states = ref<Record<string, E5State>>({})

function loadSaved() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY.value)
    if (raw) states.value = JSON.parse(raw) as Record<string, E5State>
  } catch {
    states.value = {}
  }
}

function save() {
  try {
    localStorage.setItem(STORAGE_KEY.value, JSON.stringify(states.value))
  } catch {
    // 隐私模式下 localStorage 可能不可写；答案丢失不影响判定
  }
}

async function fetchChecklist() {
  loading.value = true
  failed.value = false
  try {
    checklist.value = await personaApi.getE5Checklist(props.slug)
    loadSaved()
    await runEvaluate()
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

let timer: ReturnType<typeof setTimeout> | null = null

async function runEvaluate() {
  if (!checklist.value) return
  evaluating.value = true
  try {
    verdict.value = await personaApi.evaluateE5(states.value, props.slug)
  } catch {
    verdict.value = null
  } finally {
    evaluating.value = false
  }
}

/** 点击 → 存本地 → debounce 200ms 再问后端（连点几次不会打一串请求） */
function pick(id: string, st: E5State) {
  if (states.value[id] === st) {
    delete states.value[id] // 再点一次取消，回到"还没问"
  } else {
    states.value[id] = st
  }
  states.value = { ...states.value }
  save()
  if (timer) clearTimeout(timer)
  timer = setTimeout(runEvaluate, 200)
}

function stateOf(id: string): E5State {
  return states.value[id] ?? 'unknown'
}

function resetAll() {
  states.value = {}
  save()
  runEvaluate()
}

onMounted(fetchChecklist)
watch(() => props.slug, fetchChecklist)

const answeredCount = computed(
  () => Object.values(states.value).filter((s) => s !== 'unknown').length,
)

const total = computed(() => checklist.value?.total ?? 8)

const verdictTone = computed(() => {
  switch (verdict.value?.verdict) {
    case 'pass': return 'good'
    case 'pass_with_cost': return 'warn'
    case 'incomplete': return 'muted'
    case 'blocked': return 'bad'
    default: return 'muted'
  }
})

const progressPct = computed(() =>
  total.value ? Math.round((answeredCount.value / total.value) * 100) : 0,
)
</script>

<template>
  <section class="e5-block">
    <header class="e5-head" @click="expanded = !expanded">
      <div class="e5h-left">
        <h2>交付可行性自评</h2>
        <span class="e5h-tag">E5 · 由你填，不是我们算</span>
      </div>
      <div class="e5h-right">
        <span class="e5h-progress">{{ answeredCount }}/{{ total }} 已确认</span>
        <span class="e5h-caret">{{ expanded ? '收起' : '展开' }}</span>
      </div>
    </header>

    <p class="e5-intro">
      层高、承重、货运通道、供电、消防、吊点——这些数主办方不公开，我们抓不到，也不打算猜。
      下面每一条都附了<strong>该向主办方问的原话</strong>，照着问一遍，勾上答案即可得出结论。
    </p>

    <LoadingSkeleton v-if="loading" :lines="4" />
    <p v-else-if="failed" class="e5-fail">清单加载失败，请检查后端服务。</p>

    <template v-else-if="checklist">
      <!-- 结论条：始终可见，即使收起清单 -->
      <div v-if="verdict" class="e5-verdict" :class="`v-${verdictTone}`">
        <div class="e5v-main">
          <span class="e5v-label">{{ verdict.label }}</span>
          <span class="e5v-hint">{{ verdict.hint }}</span>
        </div>
        <span v-if="evaluating" class="e5v-busy">判定中…</span>
      </div>

      <!-- 进度条 -->
      <div class="e5-progress">
        <div class="e5p-bar"><i :style="{ width: progressPct + '%' }"></i></div>
        <button v-if="answeredCount" class="e5p-reset" @click="resetAll">重填</button>
      </div>

      <div v-show="expanded" class="e5-list">
        <article v-for="item in checklist.items" :key="item.id" class="e5-item">
          <div class="e5i-head">
            <div class="e5i-title">
              <span class="e5i-name">{{ item.name }}</span>
              <span v-if="item.short_consequence === 'block'" class="e5i-kind block">不满足则不可行</span>
              <span v-else class="e5i-kind cost">不满足则需加钱</span>
              <span v-if="!item.na_allowed" class="e5i-na-off" title="这一项任何参展方都躲不开，不能标「不适用」">
                必答
              </span>
            </div>
            <div class="e5i-btns">
              <button
                class="e5-btn ok"
                :class="{ active: stateOf(item.id) === 'ok' }"
                @click="pick(item.id, 'ok')"
              >满足</button>
              <button
                class="e5-btn short"
                :class="{ active: stateOf(item.id) === 'short' }"
                @click="pick(item.id, 'short')"
              >不满足</button>
              <button
                v-if="item.na_allowed"
                class="e5-btn na"
                :class="{ active: stateOf(item.id) === 'na' }"
                @click="pick(item.id, 'na')"
              >标摊，不适用</button>
            </div>
          </div>

          <div class="e5i-ask">
            <!-- 不加「问主办方」文字标签：后端 ask 字段本身已带这个前缀，
                 两边都写会渲染成「问主办方 问主办方：…」 -->
            <p class="e5ask-v">{{ item.ask }}</p>
          </div>

          <div class="e5i-foot">
            <span v-if="item.typical" class="e5i-typical">常见值：{{ item.typical }}</span>
            <span v-if="item.fallback" class="e5i-fallback">替代方案：{{ item.fallback }}</span>
          </div>
        </article>
      </div>

      <p class="e5-note">
        判定只发生在后端：任一条「不满足且不可行」直接否决，不做加权——
        不存在「其他项都不错所以消防不过也能凑合」。
        答案只存在你的浏览器里，不会写进展会数据。
      </p>
    </template>
  </section>
</template>

<style scoped>
.e5-block {
  background: var(--surface-0);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  margin-top: var(--spacing-md);
}
.e5-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  flex-wrap: wrap;
}
.e5h-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.e5h-left h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--ink-900);
}
.e5h-tag {
  font-size: 11px;
  color: var(--ink-500);
  background: var(--surface-1);
  border-radius: var(--radius-sm);
  padding: 2px 7px;
}
.e5h-right {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--ink-500);
}
.e5h-progress {
  font-variant-numeric: tabular-nums;
}
.e5h-caret {
  color: var(--brand-600);
  font-weight: 600;
}
.e5-intro {
  margin: 10px 0 12px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-500);
}
.e5-intro strong {
  color: var(--ink-700);
}
.e5-fail {
  font-size: 13px;
  color: var(--danger);
}

/* 结论条 */
.e5-verdict {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border-radius: var(--radius-md);
  padding: 10px 14px;
  border: 1px solid transparent;
}
.e5v-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.e5v-label {
  font-size: 14px;
  font-weight: 700;
}
.e5v-hint {
  font-size: 12px;
  line-height: 1.6;
  opacity: 0.85;
}
.e5v-busy {
  font-size: 11px;
  opacity: 0.7;
}
.v-good { background: #e8f6ef; border-color: #bce3d2; color: #0f7b52; }
.v-warn { background: #fdf3e0; border-color: #f2dcb2; color: #96620b; }
.v-bad { background: #fdeceb; border-color: #f3c9c4; color: #a52a1f; }
.v-muted { background: var(--surface-1); border-color: var(--ink-100); color: var(--ink-500); }

/* 进度 */
.e5-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 10px 0 4px;
}
.e5p-bar {
  flex: 1;
  height: 3px;
  background: var(--surface-2);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.e5p-bar i {
  display: block;
  height: 100%;
  background: var(--brand-400);
  transition: width 0.25s ease;
}
.e5p-reset {
  border: none;
  background: transparent;
  font-size: 11.5px;
  color: var(--ink-500);
  cursor: pointer;
  text-decoration: underline;
}

/* 条目 */
.e5-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 8px;
}
.e5-item {
  border-top: 1px solid var(--surface-2);
  padding: 12px 0;
}
.e5i-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.e5i-title {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.e5i-name {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--ink-900);
}
.e5i-kind {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
}
.e5i-kind.block {
  color: #a52a1f;
  background: #fdeceb;
}
.e5i-kind.cost {
  color: #96620b;
  background: #fdf3e0;
}
.e5i-na-off {
  font-size: 10px;
  color: var(--brand-600);
  background: var(--brand-50);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  cursor: help;
}
.e5i-btns {
  display: flex;
  gap: 5px;
}
.e5-btn {
  border: 1px solid var(--border-color);
  background: var(--surface-0);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  color: var(--ink-500);
  cursor: pointer;
  transition: all 0.12s ease;
}
.e5-btn:hover {
  border-color: var(--brand-300);
}
.e5-btn.ok.active {
  background: #e8f6ef;
  border-color: #bce3d2;
  color: #0f7b52;
  font-weight: 700;
}
.e5-btn.short.active {
  background: #fdeceb;
  border-color: #f3c9c4;
  color: #a52a1f;
  font-weight: 700;
}
.e5-btn.na.active {
  background: var(--surface-1);
  border-color: var(--ink-300);
  color: var(--ink-700);
  font-weight: 700;
}

.e5i-ask {
  margin-top: 7px;
  background: var(--brand-50);
  border-left: 2px solid var(--brand-300);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  padding: 7px 10px;
}
.e5ask-v {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--brand-700);
}
.e5i-foot {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--ink-500);
}
.e5i-fallback {
  color: #96620b;
}
.e5-note {
  margin: 14px 0 0;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--ink-500);
  border-top: 1px dashed var(--border-color);
  padding-top: 10px;
}
</style>
