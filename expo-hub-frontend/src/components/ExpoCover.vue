<script setup lang="ts">
import { computed, ref, watch } from 'vue'

// 展会封面：有图就出图；没有图（cover_image 为空串）或图片加载失败（404 / 跨域 / 坏地址）时，
// 自动落到品牌深蓝渐变 + 展会名水印的兜底态，页面任何位置都不再出现浏览器默认的破图图标。
// 配色与字号全部走 style.css 的品牌令牌，组件内不写死色值。
type CoverRatio = '16/9' | '4/3' | '1/1'

const props = withDefaults(defineProps<{
  /** 封面地址：真实数据里常是空串，允许为空 */
  src?: string
  /** 展会名：兜底态拿它做水印大字与左下角标题 */
  title: string
  /** 容器比例：默认 16/9；大卡、小卡、方形位可各自指定 */
  ratio?: CoverRatio
  /** 无障碍替代文本，缺省退回 title */
  alt?: string
}>(), {
  src: '',
  ratio: '16/9',
  alt: '',
})

/** 是否已加载失败：置 true 后不再渲染 <img>，同一坏地址不会被反复请求 */
const failed = ref(false)
/** 当前生效地址：失败时清空，作为「不无限重试」的第二道保险 */
const liveSrc = ref(props.src ?? '')

/** 父组件换数据（轮播切换、列表刷新）时重置失败态，新地址仍有机会正常显示 */
watch(() => props.src, (next) => {
  liveSrc.value = next ?? ''
  failed.value = false
})

/** 只有「有地址且没失败」才渲染 <img>；空串/纯空格按无图处理 */
const showImage = computed(() => !failed.value && !!liveSrc.value.trim())

/** ratio prop → CSS aspect-ratio；非法值统一退回 16/9 */
const ratioValue = computed(() => {
  const map: Record<CoverRatio, string> = { '16/9': '16 / 9', '4/3': '4 / 3', '1/1': '1 / 1' }
  return map[props.ratio] || map['16/9']
})

/** 兜底态的无障碍标签：alt 优先，其次展会名 */
const label = computed(() => props.alt || props.title || '展会封面')

/**
 * 图片加载失败：切兜底态并清空地址。
 * 清空 src 是关键——否则同一个错误地址会被留在 <img> 上反复触发加载，
 * 网络恢复或滚动重渲染时还会再打一次必然 404 的请求。
 */
function onError() {
  failed.value = true
  liveSrc.value = ''
}

/**
 * 水印大字：优先取标题里第一个汉字或字母（跳过「2026」这类开头的年份数字），
 * 标题以字母开头时取前两个字符（如 CES → CE），都没有就退回首个字符。
 */
function markOf(raw: string): string {
  const chars = Array.from(String(raw || '').trim().replace(/^[\s·\-—–_,.、，。:：/|]+/, ''))
  if (chars.length === 0) return '展'
  const hit = chars.find((c) => /[\u4e00-\u9fffA-Za-z]/.test(c))
  const first = hit || chars[0]
  if (/[A-Za-z]/.test(first)) {
    const at = chars.indexOf(first)
    const two = chars.slice(at, at + 2).join('')
    if (/^[A-Za-z]{2}$/.test(two)) return two.toUpperCase()
  }
  return first
}

const mark = computed(() => markOf(props.title))
</script>

<template>
  <!-- 容器：定位锚点 + 圆角跟随父级 + 用 aspect-ratio 控制比例 -->
  <div class="expo-cover" :style="{ aspectRatio: ratioValue }">
    <img
      v-if="showImage"
      class="cover-img"
      :src="liveSrc"
      :alt="label"
      loading="lazy"
      decoding="async"
      @error="onError"
    />

    <!-- 兜底态：深蓝渐变底 + 极淡金色径向光晕 + 展会名水印 + 左下角完整展会名 -->
    <div v-else class="cover-fallback" role="img" :aria-label="label">
      <span class="cover-glow" aria-hidden="true"></span>
      <span class="cover-mark" aria-hidden="true">{{ mark }}</span>
      <span class="cover-name">{{ title }}</span>
    </div>
  </div>
</template>

<style scoped>
.expo-cover {
  position: relative;
  overflow: hidden;
  /* 圆角不在本组件决定，跟随使用处的父容器（轮播圆角 / 卡片圆角） */
  border-radius: inherit;
  width: 100%;
  /* 兜底比例，真实比例由 ratio prop 写进 inline style 的 aspect-ratio */
  aspect-ratio: 16 / 9;
  /* 让水印字号的 cqi 以「自身宽度」为基准，随容器等比缩放 */
  container-type: inline-size;
  background: linear-gradient(150deg, var(--brand-800) 0%, var(--brand-600) 100%);
}

/* 有图态：撑满容器 + cover 裁切，构图与原先的 <img> 完全一致 */
.cover-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* ---------- 兜底态 ---------- */
.cover-fallback {
  position: absolute;
  inset: 0;
  /* 深蓝到品牌蓝的渐变，与首屏、精选卡的深色基调一致 */
  background: linear-gradient(150deg, var(--brand-800) 0%, var(--brand-600) 100%);
}

/* 极淡金色径向光晕：只做氛围，不抢文字（opacity ≤ .16） */
.cover-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(62% 62% at 78% 10%, var(--accent-500) 0%, transparent 62%);
  opacity: 0.14;
  pointer-events: none;
}

/* 水印式大字：居中、白 18%、800 字重，字号用 clamp 按容器宽度等比缩放 */
.cover-mark {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  /* 不支持容器查询单位的浏览器退回令牌字号 */
  font-size: var(--font-h1);
  font-size: clamp(var(--font-h2), 26cqi, calc(var(--font-h1) + var(--space-8)));
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.02em;
  white-space: nowrap;
  color: var(--surface-0);
  opacity: 0.18;
  user-select: none;
}

/* 左下角完整展会名：白色 0.85，最多两行，超出省略 */
.cover-name {
  position: absolute;
  left: var(--space-3);
  right: var(--space-3);
  bottom: var(--space-3);
  font-size: var(--font-sm);
  font-weight: 600;
  line-height: 1.4;
  color: rgba(255, 255, 255, 0.85);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
</style>
