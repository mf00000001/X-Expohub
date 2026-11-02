<script setup lang="ts">
import { computed } from 'vue'
import { formatStat, type PublicStats } from '@/api/stats'

// TrustStrip：Hero 正下方的浅底可信度横条。
// 口径原则：四项都与 Hero 数据带错开，且每项只对应一个可核对的数据来源；
// 只展示「拿得到且大于 0」的真实计数：任何一项缺失/为 0 就整项不渲染；
// 四项全部不可用时整条不渲染（父组件无需判断，组件自己兜底）。
const props = defineProps<{
  /** /stats/public 公开统计（可能为 null：接口失败） */
  stats?: PublicStats | null
  /** 展馆覆盖城市数：来自 GET /venues 的展馆去重城市数（父组件计算），不是展会城市数 */
  venueCityCount?: number | null
  /** 行业品类数：来自 GET /categories 的标准品类数量（父组件计算） */
  categoryCount?: number | null
}>()

interface TrustItem {
  key: string
  value: number
  label: string
}

/**
 * 四项口径（均不与 Hero 数据带的在展展会 / 入驻展商 / 在架展品重复）：
 * 1) 展馆覆盖城市：GET /venues 展馆地址去重后的城市数
 * 2) 行业品类：GET /categories 标准品类清单条数
 * 3) 微展位在线：stats.micro_booths
 * 4) 采购需求：stats.procurements
 */
const items = computed<TrustItem[]>(() => {
  const raw: TrustItem[] = [
    { key: 'venue_cities', value: props.venueCityCount ?? 0, label: '展会覆盖城市' },
    { key: 'categories', value: props.categoryCount ?? 0, label: '行业品类' },
    { key: 'micro_booths', value: props.stats?.micro_booths ?? 0, label: '微展位在线' },
  ]
  return raw.filter((it) => Number.isFinite(it.value) && it.value > 0)
})
</script>

<template>
  <section class="trust" v-if="items.length > 0">
    <div class="trust-inner">
      <div class="trust-item" v-for="it in items" :key="it.key">
        <strong>{{ formatStat(it.value) }}</strong>
        <span>{{ it.label }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.trust {
  background: var(--surface-1);
  border-bottom: 1px solid var(--ink-100);
}
.trust-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-5);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}
.trust-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-4);
}
.trust-item + .trust-item { border-left: 1px solid var(--ink-100); }
.trust-item strong {
  font-size: var(--font-h2);
  font-weight: 800;
  line-height: 1.2;
  color: var(--ink-900);
  font-variant-numeric: tabular-nums;
}
.trust-item span {
  font-size: calc(var(--font-xs) + 1px);
  color: var(--ink-500);
}

@media (max-width: 640px) {
  .trust-inner {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-4);
    padding: var(--space-4);
  }
  .trust-item { padding: 0 var(--space-2); }
  .trust-item + .trust-item { border-left: none; }
  .trust-item:nth-child(even) { border-left: 1px solid var(--ink-100); }
  .trust-item strong { font-size: var(--font-h3); }
}
</style>
