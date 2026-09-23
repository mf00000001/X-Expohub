<template>
  <view class="page-wrapper">
    <view class="flex justify-between items-center mb-4">
      <text class="page-title list-title">采购需求</text>
      <view class="btn btn-primary btn-sm" @click="goCreate">
        <text>发布采购</text>
      </view>
    </view>

    <view class="mb-6">
      <SearchBar v-model="searchKeyword" @search="handleSearch" />
    </view>

    <LoadingSkeleton v-if="loading" :lines="6" />
    <EmptyState v-else-if="procurements.length === 0" message="暂无采购需求" icon="📋" />
    <view v-else class="procurement-list">
      <ProcurementCard
        v-for="procurement in procurements"
        :key="procurement.id"
        :procurement="procurement"
        @click="goToDetail(procurement.id)"
      />
    </view>

    <view v-if="loadingMore" class="load-more">
      <text class="text-secondary">加载中...</text>
    </view>
    <view v-else-if="finished && procurements.length > 0" class="load-more">
      <text class="text-secondary">没有更多了</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onReachBottom } from '@dcloudio/uni-app'
import { procurementApi, type Procurement } from '@/api/procurement'
import ProcurementCard from '@/components/ProcurementCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'

const PAGE_SIZE = 12

const procurements = ref<Procurement[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const finished = ref(false)
const searchKeyword = ref('')
const currentPage = ref(1)

onLoad(() => {
  fetchProcurements(true)
})

onReachBottom(() => {
  if (loading.value || loadingMore.value || finished.value) return
  currentPage.value += 1
  fetchProcurements()
})

async function fetchProcurements(reset = false) {
  if (reset) {
    currentPage.value = 1
    finished.value = false
    loading.value = true
  } else {
    loadingMore.value = true
  }
  try {
    const res = (await procurementApi.getList({
      page: currentPage.value,
      page_size: PAGE_SIZE,
      search: searchKeyword.value || undefined,
    })) as any
    const items: Procurement[] = res.list || res.items || res.results || []
    procurements.value = reset ? items : procurements.value.concat(items)
    const total = res.total || 0
    const totalPages = res.totalPages || res.total_pages || Math.ceil(total / PAGE_SIZE) || 1
    finished.value = currentPage.value >= totalPages || items.length < PAGE_SIZE
  } catch (err: any) {
    uni.showToast({ title: err?.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function handleSearch(value: string) {
  searchKeyword.value = value
  fetchProcurements(true)
}

function goToDetail(id: number) {
  uni.navigateTo({ url: `/pages/procurements/detail?id=${id}` })
}

function goCreate() {
  uni.navigateTo({ url: '/pages/procurements/create' })
}
</script>

<style scoped>
.list-title {
  margin-bottom: 0;
}

.procurement-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.load-more {
  text-align: center;
  padding: 24px 0;
}
</style>
