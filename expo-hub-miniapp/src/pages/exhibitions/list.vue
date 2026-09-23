<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onShow, onReachBottom } from '@dcloudio/uni-app'
import ExpoCard from '@/components/ExpoCard.vue'
import SearchBar from '@/components/SearchBar.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'

const exhibitions = ref<Exhibition[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const finished = ref(false)
const searchKeyword = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = 9

// 后端状态值: draft/pending/published/ongoing/ended/cancelled
const statusOptions = [
  { label: '全部', value: '' },
  { label: '进行中', value: 'ongoing' },
  { label: '已发布', value: 'published' },
  { label: '即将开始', value: 'draft' },
  { label: '已结束', value: 'ended' },
]

// 防止 onShow 每次切回来都重新请求
let loaded = false

onLoad((options) => {
  // 支持外部带 search 参数进入(如搜索页)
  const q = (options?.search || options?.q || '') as string
  if (q) {
    searchKeyword.value = q
  }
})

onShow(() => {
  // 首页搜索跳转是通过 switchTab + storage 中转的,这里读取并清除
  const kw = uni.getStorageSync('search_keyword') as string
  if (kw) {
    searchKeyword.value = kw
    uni.removeStorageSync('search_keyword')
    reload()
    loaded = true
    return
  }
  if (!loaded) {
    reload()
    loaded = true
  }
})

onReachBottom(() => {
  if (loading.value || loadingMore.value || finished.value) return
  currentPage.value += 1
  fetchExhibitions()
})

async function fetchExhibitions() {
  if (currentPage.value === 1) {
    loading.value = true
  } else {
    loadingMore.value = true
  }
  try {
    const res = await exhibitionApi.getList({
      page: currentPage.value,
      page_size: pageSize,
      status: statusFilter.value || undefined,
      search: searchKeyword.value || undefined,
    })
    const items = (res as any).list || res.items || res.results || []
    if (currentPage.value === 1) {
      exhibitions.value = items
    } else {
      exhibitions.value = exhibitions.value.concat(items)
    }
    finished.value = items.length < pageSize
  } catch (err) {
    console.error('Failed to load exhibitions:', err)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function reload() {
  currentPage.value = 1
  finished.value = false
  exhibitions.value = []
  fetchExhibitions()
}

function handleSearch(value: string) {
  searchKeyword.value = value
  reload()
}

function handleFilter(status: string) {
  statusFilter.value = status
  reload()
}

function goToDetail(id: number) {
  uni.navigateTo({ url: '/pages/exhibitions/detail?id=' + id })
}
</script>

<template>
  <view class="page-wrapper">
    <text class="page-title">全部展会</text>

    <view class="flex items-center gap-4 filter-row">
      <view class="search-col">
        <SearchBar v-model="searchKeyword" @search="handleSearch" />
      </view>
    </view>

    <view class="flex gap-2 status-row">
      <view
        v-for="opt in statusOptions"
        :key="opt.value"
        :class="['btn btn-sm', statusFilter === opt.value ? 'btn-primary' : 'btn-outline']"
        @click="handleFilter(opt.value)"
      >
        <text>{{ opt.label }}</text>
      </view>
    </view>

    <LoadingSkeleton v-if="loading" :lines="6" />
    <EmptyState v-else-if="exhibitions.length === 0" message="暂无展会" icon="🎪" />
    <view v-else class="exhibition-list">
      <ExpoCard
        v-for="exhibition in exhibitions"
        :key="exhibition.id"
        :exhibition="exhibition"
        @click="goToDetail(exhibition.id)"
      />
    </view>

    <view v-if="loadingMore" class="load-more">
      <text class="text-secondary text-sm">加载中...</text>
    </view>
    <view v-else-if="!loading && finished && exhibitions.length > 0" class="load-more">
      <text class="text-secondary text-sm">没有更多了</text>
    </view>
  </view>
</template>

<style scoped>
.filter-row {
  margin-bottom: 24px;
}

.search-col {
  flex: 1;
  min-width: 0;
}

.status-row {
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.exhibition-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.load-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 0;
}
</style>
