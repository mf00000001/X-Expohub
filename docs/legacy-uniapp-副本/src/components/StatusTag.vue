<script setup lang="ts">
defineProps<{
  status: string
}>()

const statusMap: Record<string, { text: string; cls: string }> = {
  active: { text: '进行中', cls: 'tag-green' },
  upcoming: { text: '即将开始', cls: 'tag-blue' },
  ended: { text: '已结束', cls: 'tag-gray' },
  pending: { text: '待审核', cls: 'tag-yellow' },
  approved: { text: '已通过', cls: 'tag-green' },
  rejected: { text: '已拒绝', cls: 'tag-red' },
  open: { text: '开放中', cls: 'tag-green' },
  closed: { text: '已关闭', cls: 'tag-gray' },
  available: { text: '可申请', cls: 'tag-blue' },
  occupied: { text: '已占用', cls: 'tag-green' },
  reserved: { text: '已预留', cls: 'tag-yellow' },
}
</script>

<template>
  <span class="tag" :class="statusMap[status]?.cls || 'tag-gray'">
    {{ statusMap[status]?.text || status }}
  </span>
</template>
