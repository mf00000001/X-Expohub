<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from '@/composables/useI18n'

import http from '@/api/index'
const props = defineProps<{ product: Record<string, any>; manageable?: boolean }>()
const emit = defineEmits<{ (e: 'click', id: number): void; (e: 'manage-edit', id: number): void; (e: 'manage-delete', id: number): void }>()
const faved = ref(false)
function toggleFav(e: Event) {
  e.stopPropagation()
  if (!localStorage.getItem('access_token')) { alert('请先登录'); return }
  http.post('/favorites/toggle', {entity_type:'product',entity_id:props.product.id}).then((r:any)=>{ faved.value = r?.data?.favorited || r?.favorited || false }).catch(()=>{})
}
const { pick } = useI18n()

const id = computed(() => props.product.id)
const name = computed(() => pick(props.product, 'name') || '')
const PLACEHOLDER = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Crect fill=%22%23e2e8f0%22 width=%22100%22 height=%22100%22/%3E%3Ctext fill=%22%2394a3b8%22 font-size=%2240%22 x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.35em%22%3E📦%3C/text%3E%3C/svg%3E'

const image = computed(() => {
  const p = props.product
  return (p.images && Array.isArray(p.images) && p.images[0]) || p.image || p.cover_url || PLACEHOLDER
})
const category = computed(() => props.product.category || '')
const price = computed(() => props.product.price || 0)
const status = computed(() => props.product.status || '')

const statusLabelMap: Record<string, string> = {
  active: '在售', inactive: '下架', draft: '草稿', published: '已上架', ongoing: '售卖中',
}
function onEdit(e: Event) {
  e.stopPropagation()
  emit('manage-edit', id.value)
}
function onDelete(e: Event) {
  e.stopPropagation()
  emit('manage-delete', id.value)
}
</script>

<template>
  <div class="product-card card" @click="$emit('click', id)">
    <div class="product-image">
      <img :src="image" :alt="name" @error="($event.target as HTMLImageElement).src = PLACEHOLDER" />
    </div>
    <div class="product-info">
      <h4 class="product-name">{{ name }}<button class="fav-btn" @click="toggleFav" title="收藏">{{ faved ? '❤️' : '🤍' }}</button></h4>
      <span class="product-category tag tag-info">{{ category }}</span>
      <div class="product-bottom">
        <span class="product-category-text">{{ category }}</span>
        <span class="product-status tag" :class="status === 'active' ? 'tag-success' : 'tag-warning'">
          {{ statusLabelMap[status] || status }}
        </span>
      </div>
      <div v-if="manageable" class="manage-actions" @click.stop>
        <button class="btn btn-sm btn-outline" @click="onEdit">✏️ 编辑</button>
        <button class="btn btn-sm btn-danger" @click="onDelete">删除</button>
      </div>
    </div>
  </div>
</template>


<style scoped>
.product-card {
  display: flex;
  gap: var(--spacing-md);
  cursor: pointer;
  transition: transform 0.2s;
  padding: var(--spacing-md);
}
.product-card:hover {
  transform: translateY(-1px);
}

.product-image {
  width: 100px;
  height: 100px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-color);
}
.product-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.product-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  min-width: 0;
}

.product-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.product-category {
  align-self: flex-start;
}

.product-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
}

.product-price {
  font-size: 16px;
  font-weight: 600;
  color: var(--danger);
}
.fav-btn{background:none;border:none;cursor:pointer;font-size:14px;float:right;opacity:0.5}.fav-btn:hover{opacity:1}
.manage-actions { display: flex; gap: 8px; margin-top: 2px; }
</style>
