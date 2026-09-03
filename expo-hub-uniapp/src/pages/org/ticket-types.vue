<template>
  <view class="page">
    <text class="h">票种管理（主办方/管理员）</text>

    <picker :range="exhOptions" range-key="title" @change="onPickExh">
      <view class="picker">{{ curExhTitle || '选择展会' }} ▾</view>
    </picker>

    <view class="form">
      <input class="ipt" v-model="form.name" placeholder="票种名称，如：普通票" />
      <view class="row">
        <input class="ipt half" type="digit" v-model="form.price_yuan" placeholder="价格(元)，0=免费" />
        <input class="ipt half" type="number" v-model="form.quota" placeholder="数量" />
      </view>
      <input class="ipt" v-model="form.description" placeholder="说明（可选）" />
      <button class="btn" :disabled="creating" @click="create">{{ creating ? '创建中...' : '创建票种' }}</button>
    </view>

    <view class="list">
      <view class="card" v-for="t in types" :key="t.id">
        <view class="row">
          <text class="name">{{ t.name }}</text>
          <text class="price">{{ t.price_cents === 0 ? '免费' : '¥' + (t.price_cents / 100).toFixed(2) }}</text>
        </view>
        <text class="meta">余票 {{ t.remaining ?? t.quota }} / {{ t.quota }}</text>
      </view>
      <view v-if="!types.length && loaded" class="empty">该展会暂无票种</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { ticketingApi } from '@/api/ticketing'
import { request, getToken } from '@/utils/request'

const exhibitions = ref<any[]>([])
const exhIndex = ref(-1)
const exhibitionId = ref(0)
const types = ref<any[]>([])
const loaded = ref(false)
const creating = ref(false)
const form = ref({ name: '', price_yuan: '0', quota: '100', description: '' })
const exhOptions = computed(() => exhibitions.value)

onLoad(() => {
  if (!getToken()) {
    uni.reLaunch({ url: '/pages/login/login' })
    return
  }
  loadExhs()
})
onShow(() => {
  if (exhibitionId.value) loadTypes()
})

const curExhTitle = computed(() => (exhIndex.value >= 0 ? exhibitions.value[exhIndex.value]?.title : ''))

function onPickExh(e: any) {
  const i = Number(e.detail.value)
  exhIndex.value = i
  exhibitionId.value = exhibitions.value[i]?.id || 0
  loadTypes()
}

async function loadExhs() {
  try {
    const u: any = uni.getStorageSync('expo_user')
    const me = u ? JSON.parse(u) : null
    const res: any = await request({ url: '/exhibitions?page_size=100' })
    let rows = res?.list || []
    if (me && me.role !== 'admin') rows = rows.filter((x: any) => x.organizer_id === me.id)
    exhibitions.value = rows || []
  } catch (e) {
    uni.showToast({ title: '加载展会失败', icon: 'none' })
  }
}

async function loadTypes() {
  loaded.value = false
  try {
    const res: any = await ticketingApi.listTicketTypes(exhibitionId.value)
    types.value = res?.list || []
  } catch (e) {
    types.value = []
  } finally {
    loaded.value = true
  }
}

async function create() {
  if (!form.value.name.trim()) return uni.showToast({ title: '请填票种名称', icon: 'none' })
  if (!exhibitionId.value) return uni.showToast({ title: '请先选择展会', icon: 'none' })
  creating.value = true
  try {
    await ticketingApi.createTicketType({
      exhibition_id: exhibitionId.value,
      name: form.value.name.trim(),
      price_cents: Math.round((parseFloat(form.value.price_yuan) || 0) * 100),
      quota: parseInt(form.value.quota, 10) || 0,
      description: form.value.description.trim() || undefined,
    })
    uni.showToast({ title: '创建成功', icon: 'success' })
    form.value = { name: '', price_yuan: '0', quota: '100', description: '' }
    loadTypes()
  } catch (e: any) {
    uni.showToast({ title: e.message || '创建失败', icon: 'none' })
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.page { padding: 16px; background: #f5f6f8; min-height: 100vh; }
.h { font-size: 18px; font-weight: 700; display: block; margin-bottom: 12px; }
.picker { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 12px; font-size: 15px; color: #333; }
.form { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 12px; }
.ipt { border: 1px solid #e0e2e8; border-radius: 8px; padding: 9px 12px; margin-bottom: 10px; font-size: 14px; }
.half { width: 47%; }
.row { display: flex; justify-content: space-between; }
.btn { background: #4f6ef7; color: #fff; border-radius: 8px; }
.card { background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 8px; }
.name { font-size: 15px; font-weight: 600; }
.price { color: #e5484d; font-weight: 700; }
.meta { display: block; font-size: 12px; color: #999; margin-top: 4px; }
.empty { text-align: center; color: #999; padding: 24px 0; }
</style>
