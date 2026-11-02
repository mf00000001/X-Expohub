<script setup lang="ts">
/**
 * CompanyAvatar — 企业头像（无 logo 时的确定性兜底）
 *
 * micro_booths.logo_url 目前 5,000 条全为空，列表里只有文字会显得很「素」。
 * 组件按公司名做哈希，稳定地落到 6 组品牌色之一（同一家公司每次颜色都一样，
 * 不会刷新一次变一个色），中间显示公司名首字，圆形 1:1。
 *
 * - 有 logo 且能加载 → 显示图片；加载失败或为空 → 自动退回「色块 + 首字」；
 * - 纯展示、无网络请求、不落磁盘文件（图形由 CSS 渐变实时生成）；
 * - size 同时决定直径与字号，卡片 36~44、详情页 64~80 都直接传数值即可。
 */
import { computed, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 公司 / 微展位名称：决定配色与首字 */
    name?: string
    /** logo 地址（可为空串；空则直接用首字色块） */
    src?: string
    /** 直径 px，同时决定字号 */
    size?: number
    /** 无障碍标签，缺省退回 name */
    alt?: string
  }>(),
  {
    name: '',
    src: '',
    size: 40,
    alt: '',
  },
)

/**
 * 6 组品牌色（深→浅的对角渐变）。
 * 全部是深蓝体系里能挂白字的饱和度，避免彩色太跳抢走页面主色。
 */
const PALETTE: ReadonlyArray<readonly [string, string]> = [
  ['#1E3A8A', '#2563EB'], // 品牌蓝
  ['#0F766E', '#0D9488'], // 青碧
  ['#4C1D95', '#6D28D9'], // 靛紫
  ['#9A3412', '#C2410C'], // 赤陶
  ['#155E75', '#0E7490'], // 深青
  ['#831843', '#BE185D'], // 玫红
]

/** 图片加载失败标记：失败后不再渲染 <img>，避免反复请求同一个坏地址 */
const failed = ref(false)
watch(
  () => props.src,
  () => {
    failed.value = false
  },
)

const label = computed(() => props.alt || props.name || '企业')

/** 规范化名称：去空白/全角空格，用于哈希与首字 */
const cleanName = computed(() => (props.name || '').toString().replace(/[\s\u3000]+/g, ' ').trim())

/** FNV-1a 32 位哈希：按 Unicode 码点遍历，中文/emoji 也能稳定取模 */
function hash(text: string): number {
  let h = 0x811c9dc5
  for (const ch of Array.from(text)) {
    h ^= ch.codePointAt(0) ?? 0
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h
}

/** 名称 → 配色下标（空名固定第 0 组，保持中性） */
const palette = computed(() => PALETTE[cleanName.value ? hash(cleanName.value) % PALETTE.length : 0])

/** 公司名首字：跳过前导括号/引号等标点；拉丁字母统一大写 */
const initial = computed(() => {
  const stripped = cleanName.value.replace(/^[\s"'“”‘’(\[（【<《·\-—–_,.、，。:：/|]+/, '')
  const chars = Array.from(stripped)
  const hit = chars.find((c) => /[\u4e00-\u9fffA-Za-z0-9]/.test(c))
  const ch = hit || chars[0] || ''
  if (!ch) return '企'
  return /[a-z]/.test(ch) ? ch.toUpperCase() : ch
})

/** 直径：非法值退回 40，最小 16 防止挤成一条线 */
const px = computed(() => {
  const n = Number(props.size)
  return Number.isFinite(n) && n > 0 ? Math.max(16, Math.round(n)) : 40
})

/** 有地址且没失败才显示图片 */
const showImage = computed(() => !!props.src && props.src.trim().length > 0 && !failed.value)

const boxStyle = computed(() => ({
  width: `${px.value}px`,
  height: `${px.value}px`,
  borderRadius: '50%',
  background: `linear-gradient(135deg, ${palette.value[0]} 0%, ${palette.value[1]} 100%)`,
}))

const textStyle = computed(() => ({
  fontSize: `${Math.round(px.value * 0.42)}px`,
  lineHeight: '1',
}))
</script>

<template>
  <span class="company-avatar" :style="boxStyle" role="img" :aria-label="label" :title="label">
    <img
      v-if="showImage"
      class="ca-img"
      :src="src"
      :alt="label"
      loading="lazy"
      decoding="async"
      @error="failed = true"
    />
    <span v-else class="ca-initial" :style="textStyle" aria-hidden="true">{{ initial }}</span>
  </span>
</template>

<style scoped>
.company-avatar {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  color: #fff;
  /* 一圈极淡内描边，浅背景卡片上也有边界感 */
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.16);
  user-select: none;
}

.ca-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.ca-initial {
  font-weight: 700;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.94);
  text-shadow: 0 1px 1px rgba(0, 0, 0, 0.18);
}
</style>
