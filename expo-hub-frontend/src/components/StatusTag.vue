<script setup lang="ts">
interface Props {
  status: string
  size?: 'sm' | 'md'
}

defineProps<Props>()

const statusConfig: Record<string, { label: string; type: string }> = {
  // 展会状态
  draft: { label: '草稿', type: 'info' },
  pending: { label: '待审核', type: 'warning' },
  published: { label: '已发布', type: 'success' },
  ongoing: { label: '进行中', type: 'success' },
  finished: { label: '已结束', type: 'info' },
  cancelled: { label: '已取消', type: 'danger' },

  // 产品状态
  active: { label: '在售', type: 'success' },
  inactive: { label: '下架', type: 'warning' },

  // 采购状态
  open: { label: '进行中', type: 'success' },
  closed: { label: '已截止', type: 'warning' },
  matched: { label: '已匹配', type: 'info' },

  // 预订状态
  booked: { label: '已预订', type: 'info' },
  confirmed: { label: '已确认', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' },

  // 通用
  approved: { label: '已通过', type: 'success' },
}
</script>

<template>
  <span
    class="status-tag"
    :class="[
      `tag-${statusConfig[status]?.type || 'info'}`,
      size === 'sm' ? 'status-sm' : 'status-md'
    ]"
  >
    {{ statusConfig[status]?.label || status }}
  </span>
</template>

<style scoped>
.status-tag {
  display: inline-block;
  border-radius: var(--radius-full);
  font-weight: 500;
}

.status-sm {
  padding: 2px 6px;
  font-size: 11px;
}

.status-md {
  padding: 3px 10px;
  font-size: 13px;
}
</style>
