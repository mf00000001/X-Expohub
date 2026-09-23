<template>
  <view class="page-wrapper">
    <view class="card card-body">
      <view class="form-group">
        <text class="form-label">关联展会（可选）</text>
        <picker :range="exhibitionOptions" :value="exhibitionIndex" @change="onExhibitionChange">
          <view class="form-input picker-value">
            <text :class="exhibitionIndex === 0 ? 'text-secondary' : ''">{{ exhibitionOptions[exhibitionIndex] }}</text>
          </view>
        </picker>
      </view>

      <view class="form-group">
        <text class="form-label">采购标题 <text class="text-danger">*</text></text>
        <input cursor-spacing="24"
          v-model="form.title"
          class="form-input"
          type="text"
          placeholder="例如：需要采购100台智能传感器"
        />
      </view>

      <view class="form-group">
        <text class="form-label">详细描述 <text class="text-danger">*</text></text>
        <textarea cursor-spacing="24"
          v-model="form.description"
          class="form-input form-textarea"
          placeholder="请详细描述您需要的产品规格、要求等..."
        />
      </view>

      <view class="form-row">
        <view class="form-group form-col">
          <text class="form-label">品类</text>
          <input cursor-spacing="24" v-model="form.category" class="form-input" type="text" placeholder="如：电子产品、机械设备..." />
        </view>
        <view class="form-group form-col">
          <text class="form-label">数量</text>
          <input cursor-spacing="24" v-model="form.quantity" class="form-input" type="number" placeholder="1" />
        </view>
      </view>

      <view class="form-row">
        <view class="form-group form-col">
          <text class="form-label">单位</text>
          <input cursor-spacing="24" v-model="form.unit" class="form-input" type="text" placeholder="如：台、件、套..." />
        </view>
        <view class="form-group form-col">
          <text class="form-label">预算金额</text>
          <input cursor-spacing="24" v-model="form.budget" class="form-input" type="digit" placeholder="0.00" />
        </view>
      </view>

      <view class="form-group">
        <text class="form-label">截止日期</text>
        <picker mode="date" :value="form.deadline" @change="onDeadlineChange">
          <view class="form-input picker-value">
            <text :class="form.deadline ? '' : 'text-secondary'">{{ form.deadline || '请选择截止日期' }}</text>
          </view>
        </picker>
      </view>

      <view class="flex gap-2 mt-6">
        <view class="btn btn-primary btn-lg flex-1" :class="{ 'btn-disabled': submitting }" @click="handleSubmit">
          <text>{{ submitting ? '发布中...' : '立即发布' }}</text>
        </view>
        <view class="btn btn-outline btn-lg flex-1" @click="goBack">
          <text>取消</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { procurementApi } from '@/api/procurement'
import { requireLogin } from '@/utils/auth-guard'

const submitting = ref(false)
const exhibitions = ref<Exhibition[]>([])
const exhibitionOptions = ref<string[]>(['不关联展会'])
const exhibitionIndex = ref(0)

const form = reactive({
  exhibition_id: '' as string | number,
  title: '',
  description: '',
  category: '',
  quantity: '',
  unit: '',
  budget: '',
  deadline: '',
})

onLoad(() => {
  // 未登录跳登录页，避免发布时刷 401
  if (!requireLogin()) return
  fetchExhibitions()
})

async function fetchExhibitions() {
  try {
    const res = (await exhibitionApi.getList({ page: 1, page_size: 100, status: 'active' })) as any
    exhibitions.value = res.list || res.items || res.results || []
    exhibitionOptions.value = ['不关联展会', ...exhibitions.value.map((e) => e.title)]
  } catch (err) {
    // 拉取展会失败不阻塞发布表单
  }
}

function onExhibitionChange(e: any) {
  exhibitionIndex.value = Number(e.detail.value)
  const ex = exhibitions.value[exhibitionIndex.value - 1]
  form.exhibition_id = ex ? ex.id : ''
}

function onDeadlineChange(e: any) {
  form.deadline = e.detail.value
}

async function handleSubmit() {
  if (!form.title.trim()) {
    uni.showToast({ title: '请输入采购标题', icon: 'none' })
    return
  }
  if (!form.description.trim()) {
    uni.showToast({ title: '请输入采购描述', icon: 'none' })
    return
  }
  if (submitting.value) return
  submitting.value = true
  uni.showLoading({ title: '发布中' })
  try {
    const payload: Record<string, unknown> = {
      title: form.title.trim(),
      description: form.description.trim(),
      category: form.category.trim() || undefined,
      unit: form.unit.trim() || undefined,
    }
    if (form.exhibition_id) payload.exhibition_id = Number(form.exhibition_id)
    if (form.quantity !== '') payload.quantity = Number(form.quantity)
    if (form.budget !== '') payload.budget = Number(form.budget)
    if (form.deadline) payload.deadline = form.deadline
    await procurementApi.create(payload)
    uni.hideLoading()
    uni.showToast({ title: '发布成功', icon: 'success' })
    setTimeout(() => {
      uni.navigateBack()
    }, 1000)
  } catch (err: any) {
    uni.hideLoading()
    uni.showToast({ title: err?.message || '发布失败，请重试', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function goBack() {
  uni.navigateBack()
}
</script>

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
