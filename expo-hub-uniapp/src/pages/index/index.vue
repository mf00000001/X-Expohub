<template>
  <view class="page">
    <view class="topbar">
      <text class="brand">ExpoHub 小程序</text>
      <view v-if="!user" class="btn-login" @click="goLogin">登录</view>
      <view v-else class="user-chip">
        <text>{{ user.username }}（{{ roleLabel }}）</text>
        <text class="logout" @click="doLogout">退出</text>
      </view>
    </view>

    <view class="actions" v-if="user">
      <view class="act" @click="goMyTickets">
        <text class="act-icon">🎫</text><text>我的票务</text>
      </view>
      <view class="act" v-if="isStaff" @click="go('/pages/org/ticket-types')">
        <text class="act-icon">🏷️</text><text>票种管理</text>
      </view>
      <view class="act" v-if="isStaff" @click="go('/pages/org/onsite')">
        <text class="act-icon">✅</text><text>现场核销</text>
      </view>
    </view>

    <view class="list">
      <view class="card" v-for="e in exhibitions" :key="e.id" @click="goShop(e)">
        <text class="title">{{ e.title }}</text>
        <text class="meta">📅 {{ (e.start_date || '').slice(0, 10) }} ~ {{ (e.end_date || '').slice(0, 10) }}</text>
        <text class="meta">📍 {{ e.location }}</text>
        <view class="row">
          <text class="tag">{{ statusMap[e.status] || e.status }}</text>
          <text class="buy-btn" v-if="canBuy(e)">购买门票 ›</text>
        </view>
      </view>
      <view v-if="!exhibitions.length" class="empty">暂无展会</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { request, getToken, logoutLocal } from '@/utils/request'

const exhibitions = ref<any[]>([])
const user = ref<any>(null)
const roleLabelMap: Record<string, string> = { admin: '管理员', organizer: '主办方', exhibitor: '展商', buyer: '买家', visitor: '游客' }
const roleLabel = computed(() => roleLabelMap[user.value?.role] || user.value?.role || '')
const isStaff = computed(() => user.value && (user.value.role === 'organizer' || user.value.role === 'admin'))
const statusMap: Record<string, string> = { published: '已发布', ongoing: '进行中', ended: '已结束' }

onShow(() => {
  const raw = uni.getStorageSync('expo_user') as string
  user.value = raw ? JSON.parse(raw) : null
  load()
})

async function load() {
  try {
    const res: any = await request({ url: '/exhibitions?page_size=50', auth: false })
    exhibitions.value = res?.list || []
  } catch (e) {
    uni.showToast({ title: '加载展会失败', icon: 'none' })
  }
}
function canBuy(e: any) {
  return e.status === 'published' || e.status === 'ongoing'
}
function goShop(e: any) {
  uni.navigateTo({ url: '/pages/tickets/shop?exhibitionId=' + e.id + '&title=' + encodeURIComponent(e.title) })
}
function goMyTickets() {
  if (!getToken()) return goLogin()
  uni.navigateTo({ url: '/pages/tickets/my' })
}
function goLogin() {
  uni.navigateTo({ url: '/pages/login/login' })
}
function go(url: string) {
  uni.navigateTo({ url })
}
function doLogout() {
  logoutLocal()
  user.value = null
  uni.showToast({ title: '已退出', icon: 'none' })
}
</script>

<style scoped>
.page { padding: 16px; background: #f5f6f8; min-height: 100vh; }
.topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.brand { font-size: 18px; font-weight: 700; }
.btn-login { padding: 4px 14px; border-radius: 20px; background: #4f6ef7; color: #fff; font-size: 13px; }
.user-chip { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #333; }
.logout { color: #999; margin-left: 8px; }
.actions { display: flex; gap: 10px; margin-bottom: 12px; }
.act { flex: 1; background: #fff; border-radius: 10px; padding: 12px 0; display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 13px; }
.act-icon { font-size: 20px; }
.card { background: #fff; border-radius: 10px; padding: 14px; margin-bottom: 10px; }
.title { font-size: 16px; font-weight: 600; display: block; margin-bottom: 6px; }
.meta { display: block; font-size: 12px; color: #666; margin-top: 2px; }
.row { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.tag { font-size: 11px; color: #4f6ef7; background: #eef1fe; padding: 2px 8px; border-radius: 8px; }
.buy-btn { font-size: 13px; color: #e5484d; }
.empty { text-align: center; color: #999; padding: 40px 0; }
</style>
