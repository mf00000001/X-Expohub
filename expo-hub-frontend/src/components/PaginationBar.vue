<script setup lang="ts">
/**
 * 通用分页组件 PaginationBar
 *
 * 设计要点（对齐现有页面的历史问题）：
 * 1. 页码窗口化 —— 旧写法 `v-for="page in totalPages"` 在 10027 件展品 / 9 条一页时
 *    会渲染 1114 个按钮，本组件只渲染「首页 + 当前页±N + 末页 + 省略号」。
 * 2. 每页条数可切换，并把选择结果记住（storageKey），换页时自动回到第 1 页。
 * 3. 跳页输入框 + 总数文案，让「数据到底有多少」一眼可见（这正是微展位广场此前缺失的）。
 * 4. 移动端折叠为「上一页 / 第 x 页 共 y 页 / 下一页」，避免按钮换行挤压。
 * 5. 纯展示组件：不请求数据，翻页由父级 v-model:page 驱动。
 *
 * 用法：
 *   <PaginationBar
 *     v-model:page="page" v-model:page-size="pageSize"
 *     :total="total" :loading="loading" storage-key="mb-list-page-size"
 *     :page-size-options="[12, 24, 48]" @change="fetchList" />
 */
import { computed, ref, watch } from 'vue'

type PageItem = number | 'left-ellipsis' | 'right-ellipsis'

const props = withDefaults(defineProps<{
  /** 当前页（v-model:page） */
  page: number
  /** 总条数，用于「共 N 条」文案 */
  total?: number
  /** 总页数；未传时按 total/pageSize 推导 */
  totalPages?: number
  /** 每页条数（v-model:page-size） */
  pageSize?: number
  /** 可选的每页条数 */
  pageSizeOptions?: number[]
  /** 当前页左右各显示几个页码 */
  sibling?: number
  showTotal?: boolean
  showJump?: boolean
  showPageSize?: boolean
  /** 请求中：禁用交互并降透明度 */
  loading?: boolean
  /** 计数单位 */
  unit?: string
  /** 进度条下方是否展示"第 x / y 页" */
  showPageInfo?: boolean
  /** 翻页后平滑回顶 */
  scrollTop?: boolean
  /** 传入后把每页条数写入 localStorage 记住用户选择 */
  storageKey?: string
}>(), {
  total: undefined,
  totalPages: undefined,
  pageSize: undefined,
  pageSizeOptions: () => [12, 24, 48, 96],
  sibling: 1,
  showTotal: true,
  showJump: true,
  showPageSize: true,
  loading: false,
  unit: '条',
  showPageInfo: true,
  scrollTop: true,
  storageKey: '',
})

const emit = defineEmits<{
  (e: 'update:page', value: number): void
  (e: 'update:pageSize', value: number): void
  (e: 'change', payload: { page: number; pageSize: number }): void
}>()

/** 总页数：优先用后端 totalPages，其次 total/pageSize 推导，兜底 1 */
const pageCount = computed(() => {
  const explicit = Number(props.totalPages)
  if (Number.isFinite(explicit) && explicit > 0) return Math.trunc(explicit)
  if (props.total != null && props.pageSize) {
    return Math.max(1, Math.ceil(Number(props.total) / Number(props.pageSize)))
  }
  return 1
})

/** 容错：父级传入越界页码时按边界收敛，避免出现"当前页 3 / 共 2 页" */
const currentPage = computed(() => {
  const p = Math.trunc(Number(props.page) || 1)
  return Math.min(Math.max(1, p), pageCount.value)
})

const totalText = computed(() =>
  props.total == null ? '' : Number(props.total).toLocaleString('zh-CN')
)

const sizeOptions = computed(() => {
  const base = [...(props.pageSizeOptions || [])]
  if (props.pageSize && !base.includes(props.pageSize)) base.push(props.pageSize)
  return base.sort((a, b) => a - b)
})

/** 页码窗口：1 … 4 5 6 … 20 */
const pageItems = computed<PageItem[]>(() => {
  const total = pageCount.value
  const cur = currentPage.value
  const s = Math.max(0, Math.trunc(props.sibling))
  const windowSize = s * 2 + 1
  if (total <= windowSize + 2) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  let start = Math.max(2, cur - s)
  let end = Math.min(total - 1, cur + s)

  // 靠边时补足窗口宽度，保证可点页码数量稳定
  const need = windowSize - (end - start + 1)
  if (need > 0) {
    if (start === 2) end = Math.min(total - 1, end + need)
    else if (end === total - 1) start = Math.max(2, start - need)
  }

  const out: PageItem[] = [1]
  if (start > 2) out.push('left-ellipsis')
  for (let p = start; p <= end; p++) out.push(p)
  if (end < total - 1) out.push('right-ellipsis')
  out.push(total)
  return out
})

const canPrev = computed(() => currentPage.value > 1 && !props.loading)
const canNext = computed(() => currentPage.value < pageCount.value && !props.loading)

function go(target: number) {
  if (props.loading) return
  const p = Math.min(Math.max(1, Math.trunc(Number(target) || 1)), pageCount.value)
  if (p === props.page) return
  emit('update:page', p)
  emit('change', { page: p, pageSize: Number(props.pageSize) || 0 })
  if (props.scrollTop) {
    try { window.scrollTo({ top: 0, behavior: 'smooth' }) } catch { window.scrollTo(0, 0) }
  }
}

function onPageSizeChange(e: Event) {
  const size = Number((e.target as HTMLSelectElement).value)
  if (!Number.isFinite(size) || size <= 0 || size === props.pageSize) return
  emit('update:pageSize', size)
  if (props.storageKey) {
    try { localStorage.setItem(props.storageKey, String(size)) } catch { /* 隐私模式忽略 */ }
  }
  // 每页条数变化后旧页码会失真，统一回到第 1 页
  if (props.page !== 1) emit('update:page', 1)
  emit('change', { page: 1, pageSize: size })
  if (props.scrollTop) {
    try { window.scrollTo({ top: 0, behavior: 'smooth' }) } catch { window.scrollTo(0, 0) }
  }
}

const jumpValue = ref('')
watch(() => props.page, () => { jumpValue.value = '' })

function submitJump() {
  const raw = jumpValue.value.trim()
  if (!raw) return
  const n = Number(raw)
  jumpValue.value = ''
  if (!Number.isFinite(n)) return
  go(n)
}
</script>

<template>
  <nav v-if="pageCount > 1 || (showTotal && total)" class="pager" :class="{ 'is-loading': loading }" aria-label="分页导航">
    <div class="pager-meta">
      <span v-if="showTotal && totalText" class="pager-total">
        共 <strong>{{ totalText }}</strong> {{ unit }}
        <template v-if="showPageInfo">· 第 {{ currentPage }} / {{ pageCount }} 页</template>
      </span>
      <span v-else-if="showPageInfo" class="pager-total">第 {{ currentPage }} / {{ pageCount }} 页</span>

      <label v-if="showPageSize" class="pager-size">
        每页
        <select :value="pageSize" :disabled="loading" @change="onPageSizeChange">
          <option v-for="s in sizeOptions" :key="s" :value="s">{{ s }}</option>
        </select>
        {{ unit }}
      </label>
    </div>

    <div class="pager-nav">
      <!-- 桌面端：完整页码 -->
      <div class="pager-full">
        <button class="pg-btn" :disabled="!canPrev" title="第一页" aria-label="第一页" @click="go(1)">«</button>
        <button class="pg-btn" :disabled="!canPrev" @click="go(currentPage - 1)">‹ 上一页</button>

        <template v-for="item in pageItems" :key="item">
          <span v-if="typeof item === 'string'" class="pg-dots" aria-hidden="true">…</span>
          <button
            v-else
            class="pg-btn pg-num"
            :class="{ active: item === currentPage }"
            :aria-current="item === currentPage ? 'page' : undefined"
            :disabled="loading"
            @click="go(item)"
          >{{ item }}</button>
        </template>

        <button class="pg-btn" :disabled="!canNext" @click="go(currentPage + 1)">下一页 ›</button>
        <button class="pg-btn" :disabled="!canNext" title="最后一页" aria-label="最后一页" @click="go(pageCount)">»</button>
      </div>

      <!-- 移动端：折叠为上一页/页码/下一页 -->
      <div class="pager-compact">
        <button class="pg-btn" :disabled="!canPrev" @click="go(currentPage - 1)">‹ 上一页</button>
        <span class="pg-compact-info">{{ currentPage }} / {{ pageCount }}</span>
        <button class="pg-btn" :disabled="!canNext" @click="go(currentPage + 1)">下一页 ›</button>
      </div>
    </div>

    <div v-if="showJump" class="pager-jump">
      跳至
      <input
        v-model="jumpValue"
        class="pg-input"
        type="number"
        inputmode="numeric"
        min="1"
        :max="pageCount"
        :disabled="loading"
        aria-label="跳转到指定页"
        @keyup.enter="submitJump"
        @blur="submitJump"
      />
      页
    </div>
  </nav>
</template>

<style scoped>
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-top: 28px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}
.pager.is-loading { opacity: 0.65; }
.pager.is-loading .pg-btn,
.pager.is-loading .pg-input { cursor: progress; }

.pager-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-secondary);
}
.pager-total strong { color: var(--primary); font-size: 14px; }
.pager-size { display: inline-flex; align-items: center; gap: 6px; }
.pager-size select {
  height: 30px;
  padding: 0 6px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-white);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
}
.pager-size select:focus { outline: none; border-color: var(--primary); }

.pager-nav { display: flex; align-items: center; }
.pager-full { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.pager-compact { display: none; align-items: center; gap: 10px; }
.pg-compact-info { font-size: 13px; color: var(--text-secondary); white-space: nowrap; }

.pg-btn {
  height: 32px;
  min-width: 32px;
  padding: 0 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-white);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  line-height: 1;
  cursor: pointer;
  transition: all 0.15s ease;
}
.pg-btn:hover:not(:disabled) {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
}
.pg-btn:focus-visible { outline: 2px solid var(--primary); outline-offset: 1px; }
.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pg-num { padding: 0 6px; font-variant-numeric: tabular-nums; }
.pg-num.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  font-weight: 700;
  cursor: default;
}
.pg-num.active:hover { background: var(--primary); color: #fff; }
.pg-dots {
  padding: 0 2px;
  color: var(--text-hint);
  font-size: 13px;
  user-select: none;
}

.pager-jump {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}
.pg-input {
  width: 56px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-white);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  text-align: center;
}
.pg-input:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-light); }
/* 去掉数字输入框的上下箭头，避免 32px 高度被撑开 */
.pg-input::-webkit-outer-spin-button,
.pg-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.pg-input[type='number'] { -moz-appearance: textfield; appearance: textfield; }

@media (max-width: 720px) {
  .pager { justify-content: center; }
  .pager-full, .pager-jump { display: none; }
  .pager-compact { display: flex; }
  .pager-meta { justify-content: center; width: 100%; }
}
</style>
