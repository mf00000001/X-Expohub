<script setup lang="ts">
import { ref, reactive } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { boothApi } from '@/api/booth'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'

const submitting = ref(false)

const exhibitions = ref<Exhibition[]>([])
const exhibitionOptions = ref<string[]>(['选择展会'])
const exhibitionIndex = ref(0)

const statusOptions = ['可申请', '已预定', '已占用']
const statusValues = ['available', 'booked', 'occupied']
const statusIndex = ref(0)

const form = reactive({
  booth_number: '',
  size: '',
  location_area: '',
  price: '',
  company_name: '',
  description: '',
})

onLoad((options) => {
  if (options?.exhibition_id) {
    const idx = Number(options.exhibition_id)
    // 展会列表加载后再回填
    pendingExhibitionId = idx
  }
  loadExhibitions()
})

// 从 booth-edit?exhibition_id=X 跳转时回填的展会 id
let pendingExhibitionId: number | null = null

async function loadExhibitions() {
  try {
    const res = (await exhibitionApi.getList({ page: 1, page_size: 100 })) as any
    exhibitions.value = res.list || res.items || res.results || []
    exhibitionOptions.value = ['选择展会', ...exhibitions.value.map((e) => e.title)]
    if (pendingExhibitionId) {
      const i = exhibitions.value.findIndex((e) => e.id === pendingExhibitionId)
      if (i >= 0) exhibitionIndex.value = i + 1
      pendingExhibitionId = null
    }
  } catch (err) {
    uni.showToast({ title: '展会列表加载失败', icon: 'none' })
  }
}

function onExhibitionChange(e: any) {
  exhibitionIndex.value = Number(e.detail.value)
}

function onStatusChange(e: any) {
  statusIndex.value = Number(e.detail.value)
}

async function handleSave() {
  const ex = exhibitions.value[exhibitionIndex.value - 1]
  if (!ex) {
    uni.showToast({ title: '请选择所属展会', icon: 'none' })
    return
  }
  if (!form.booth_number.trim()) {
    uni.showToast({ title: '请输入展位号', icon: 'none' })
    return
  }
  if (submitting.value) return
  submitting.value = true
  uni.showLoading({ title: '保存中' })
  try {
    const payload: Record<string, unknown> = {
      exhibition_id: ex.id,
      booth_number: form.booth_number.trim(),
      size: form.size.trim() || undefined,
      location_area: form.location_area.trim() || undefined,
      price: form.price !== '' ? Number(form.price) : undefined,
      company_name: form.company_name.trim() || undefined,
      description: form.description.trim() || undefined,
      status: statusValues[statusIndex.value],
    }
    await boothApi.create(payload)
    uni.hideLoading()
    uni.showToast({ title: '创建成功', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 800)
  } catch (err: any) {
    uni.hideLoading()
    uni.showToast({ title: err?.message || '保存失败，请重试', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function goBack() {
  uni.navigateBack()
}
</script>

<template>
  <view class="page-wrapper">
    <view class="card card-body">
      <view class="form-group">
        <text class="form-label">所属展会 <text class="text-danger">*</text></text>
        <picker :range="exhibitionOptions" :value="exhibitionIndex" @change="onExhibitionChange">
          <view class="form-input picker-value">
            <text :class="exhibitionIndex === 0 ? 'text-secondary' : ''">{{ exhibitionOptions[exhibitionIndex] }}</text>
          </view>
        </picker>
      </view>

      <view class="form-group">
        <text class="form-label">展位号 <text class="text-danger">*</text></text>
        <input
          v-model="form.booth_number"
          class="form-input"
          type="text"
          placeholder="如：A-001"
          cursor-spacing="24"
        />
      </view>

      <view class="form-row">
        <view class="form-group form-col">
          <text class="form-label">面积</text>
          <input
            v-model="form.size"
            class="form-input"
            type="text"
            placeholder="如：9x9m"
            cursor-spacing="24"
          />
        </view>
        <view class="form-group form-col">
          <text class="form-label">价格（元）</text>
          <input
            v-model="form.price"
            class="form-input"
            type="digit"
            placeholder="0.00"
            cursor-spacing="24"
          />
        </view>
      </view>

      <view class="form-group">
        <text class="form-label">所在区域</text>
        <input
          v-model="form.location_area"
          class="form-input"
          type="text"
          placeholder="如：A区主厅"
          cursor-spacing="24"
        />
      </view>

      <view class="form-group">
        <text class="form-label">预分配展商（可选，留空=待申请）</text>
        <input
          v-model="form.company_name"
          class="form-input"
          type="text"
          placeholder="公司名称"
          cursor-spacing="24"
        />
      </view>

      <view class="form-group">
        <text class="form-label">状态</text>
        <picker :range="statusOptions" :value="statusIndex" @change="onStatusChange">
          <view class="form-input picker-value">
            <text>{{ statusOptions[statusIndex] }}</text>
          </view>
        </picker>
      </view>

      <view class="form-group">
        <text class="form-label">展位描述</text>
        <textarea
          v-model="form.description"
          class="form-input form-textarea"
          placeholder="位置优势、开放面等..."
          cursor-spacing="24"
        />
      </view>

      <view class="flex gap-2 mt-6">
        <view class="btn btn-primary btn-lg flex-1" :class="{ 'btn-disabled': submitting }" @click="handleSave">
          <text>{{ submitting ? '保存中...' : '保存' }}</text>
        </view>
        <view class="btn btn-outline btn-lg flex-1" @click="goBack">
          <text>取消</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.picker-value {
  display: flex;
  align-items: center;
  min-height: 44px;
  box-sizing: border-box;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-col {
  flex: 1;
  min-width: 0;
}
</style>
