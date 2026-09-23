<script setup lang="ts">
import { ref, reactive } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'

const editingId = ref<number | null>(null)
const submitting = ref(false)

const statusOptions = ['草稿', '待审批', '发布']
const statusValues = ['draft', 'pending', 'published']
const statusIndex = ref(0)

const form = reactive({
  title: '',
  cover_image: '',
  start_date: '',
  end_date: '',
  location: '',
  description: '',
})

onLoad((options) => {
  const id = options?.id ? Number(options.id) : null
  editingId.value = id
  if (id) loadExhibition(id)
})

async function loadExhibition(id: number) {
  uni.showLoading({ title: '加载中' })
  try {
    const ex = (await exhibitionApi.getById(id)) as Exhibition
    form.title = ex.title || ''
    form.cover_image = ex.cover_image || ''
    form.start_date = ex.start_date || ''
    form.end_date = ex.end_date || ''
    form.location = ex.location || ''
    form.description = ex.description || ''
    const si = statusValues.indexOf(ex.status)
    if (si >= 0) statusIndex.value = si
  } catch (err: any) {
    uni.showToast({ title: err?.message || '加载失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

function onStartDateChange(e: any) {
  form.start_date = e.detail.value
}

function onEndDateChange(e: any) {
  form.end_date = e.detail.value
}

function onStatusChange(e: any) {
  statusIndex.value = Number(e.detail.value)
}

function buildPayload(): Record<string, unknown> {
  return {
    title: form.title.trim(),
    cover_image: form.cover_image.trim() || undefined,
    start_date: form.start_date,
    end_date: form.end_date,
    location: form.location.trim(),
    description: form.description.trim() || undefined,
    status: statusValues[statusIndex.value],
  }
}

async function handleSave() {
  if (!form.title.trim()) {
    uni.showToast({ title: '请输入展会名称', icon: 'none' })
    return
  }
  if (!form.start_date || !form.end_date) {
    uni.showToast({ title: '请选择起止日期', icon: 'none' })
    return
  }
  if (!form.location.trim()) {
    uni.showToast({ title: '请输入举办地点', icon: 'none' })
    return
  }
  if (submitting.value) return
  submitting.value = true
  uni.showLoading({ title: '保存中' })
  try {
    const payload = buildPayload()
    if (editingId.value) await exhibitionApi.update(editingId.value, payload)
    else await exhibitionApi.create(payload)
    uni.hideLoading()
    uni.showToast({ title: '保存成功', icon: 'success' })
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
        <text class="form-label">展会名称 <text class="text-danger">*</text></text>
        <input
          v-model="form.title"
          class="form-input"
          type="text"
          placeholder="请输入展会名称"
          cursor-spacing="24"
        />
      </view>

      <view class="form-group">
        <text class="form-label">封面图片URL</text>
        <input
          v-model="form.cover_image"
          class="form-input"
          type="text"
          placeholder="https://example.com/cover.jpg"
          cursor-spacing="24"
        />
      </view>

      <view class="form-row">
        <view class="form-group form-col">
          <text class="form-label">开始日期 <text class="text-danger">*</text></text>
          <picker mode="date" :value="form.start_date" @change="onStartDateChange">
            <view class="form-input picker-value">
              <text :class="form.start_date ? '' : 'text-secondary'">{{ form.start_date || '请选择' }}</text>
            </view>
          </picker>
        </view>
        <view class="form-group form-col">
          <text class="form-label">结束日期 <text class="text-danger">*</text></text>
          <picker mode="date" :value="form.end_date" @change="onEndDateChange">
            <view class="form-input picker-value">
              <text :class="form.end_date ? '' : 'text-secondary'">{{ form.end_date || '请选择' }}</text>
            </view>
          </picker>
        </view>
      </view>

      <view class="form-group">
        <text class="form-label">举办地点 <text class="text-danger">*</text></text>
        <input
          v-model="form.location"
          class="form-input"
          type="text"
          placeholder="如：广州国际会展中心"
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
        <text class="form-label">展会介绍</text>
        <textarea
          v-model="form.description"
          class="form-input form-textarea"
          placeholder="展会主题、规模、展品范围等..."
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
