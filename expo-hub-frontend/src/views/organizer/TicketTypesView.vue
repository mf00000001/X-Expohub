<script setup lang="ts">
// 票种管理（主办方/管理员）：为指定展会创建票种 + 查看列表
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ticketingApi, type TicketTypeItem } from '@/api/ticketing'
import { exhibitionApi } from '@/api/exhibition'

const route = useRoute()
const exhibitionId = ref<number>(Number(route.query.exhibitionId) || 0)

const list = ref<TicketTypeItem[]>([])
const loading = ref(false)
const message = ref('')
const exTitle = ref('')

const form = ref({ name: '', price_yuan: '0', quota: '100', description: '' })

async function load() {
  if (!exhibitionId.value) return
  loading.value = true
  try {
    const res = await ticketingApi.listTicketTypes(exhibitionId.value)
    list.value = res.list || []
    const ex: any = await exhibitionApi.getDetail(exhibitionId.value)
    exTitle.value = ex?.title || ''
  } catch (e: any) {
    message.value = e?.response?.data?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function create() {
  message.value = ''
  if (!form.value.name.trim()) {
    message.value = '请填写票种名称'
    return
  }
  try {
    const tt = await ticketingApi.createTicketType({
      exhibition_id: exhibitionId.value,
      name: form.value.name.trim(),
      price_cents: Math.round(parseFloat(form.value.price_yuan || '0') * 100),
      quota: parseInt(form.value.quota || '0', 10) || 0,
      description: form.value.description.trim() || undefined
    })
    list.value = [...list.value, tt]
    form.value = { name: '', price_yuan: '0', quota: '100', description: '' }
    message.value = '票种创建成功'
  } catch (e: any) {
    message.value = e?.response?.data?.message || '创建失败'
  }
}

function yuan(c: number): string {
  return c === 0 ? '免费' : `¥${(c / 100).toFixed(2)}`
}

onMounted(load)
</script>

<template>
  <div class="container main-content">
    <div class="flex justify-between items-center mb-md">
      <h2>🎟️ 票种管理{{ exTitle ? ` · ${exTitle}` : '' }}</h2>
      <a class="btn btn-outline btn-sm" href="/exhibitions" @click.prevent>← 展会列表</a>
    </div>

    <div class="flex items-center gap-sm mb-md">
      <label class="form-label mb-0">展会 ID：</label>
      <input v-model.number="exhibitionId" class="form-input" type="number" style="max-width: 120px" />
      <button class="btn btn-outline btn-sm" @click="load">加载</button>
    </div>

    <p v-if="message" :class="message.includes('成功') ? 'tag tag-success' : 'form-error'">{{ message }}</p>

    <div class="card p-md mb-md">
      <h3 class="mb-sm">新增票种</h3>
      <div class="flex gap-md flex-wrap">
        <div class="flex-1">
          <label class="form-label">名称</label>
          <input v-model="form.name" class="form-input" placeholder="早鸟票 / 普通票 / 免费票" />
        </div>
        <div class="flex-1">
          <label class="form-label">价格（元，0=免费）</label>
          <input v-model="form.price_yuan" class="form-input" type="number" min="0" step="0.01" />
        </div>
        <div class="flex-1">
          <label class="form-label">名额</label>
          <input v-model="form.quota" class="form-input" type="number" min="1" />
        </div>
      </div>
      <div class="mt-sm">
        <label class="form-label">描述</label>
        <input v-model="form.description" class="form-input" placeholder="选填" />
      </div>
      <button class="btn btn-primary mt-md" @click="create">创建票种</button>
    </div>

    <div class="card p-md">
      <h3 class="mb-sm">已售票种（{{ list.length }}）</h3>
      <p v-if="loading">加载中…</p>
      <div v-for="tt in list" :key="tt.id" class="flex justify-between items-center mb-sm">
        <div>
          <span class="tag tag-info mr-sm">#{{ tt.id }}</span>
          <strong>{{ tt.name }}</strong>
          <span :class="tt.price_cents === 0 ? 'tag tag-success' : 'tag tag-warning'">{{ yuan(tt.price_cents) }}</span>
        </div>
        <span class="tag">余票 {{ tt.quota }}</span>
      </div>
      <div v-if="!loading && list.length === 0" class="form-error">暂无票种</div>
    </div>
  </div>
</template>
