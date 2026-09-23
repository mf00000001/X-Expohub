<script setup lang="ts">
import { ref, reactive } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { productApi, type Product } from '@/api/product'
import { boothApi, type Booth } from '@/api/booth'

const editingId = ref<number | null>(null)
const submitting = ref(false)

const booths = ref<Booth[]>([])
const boothOptions = ref<string[]>(['不关联展位'])
const boothIndex = ref(0)

const statusOptions = ['草稿', '上架']
const statusIndex = ref(1) // 默认上架

const form = reactive({
  name: '',
  booth_id: '' as string | number,
  category: '',
  price: '',
  images: '',
  description: '',
})

onLoad((options) => {
  const id = options?.id ? Number(options.id) : null
  editingId.value = id
  loadBooths()
  if (id) loadProduct(id)
})

async function loadBooths() {
  try {
    const res = (await boothApi.getMyBooths({ page: 1, page_size: 50 })) as any
    booths.value = res.list || res.items || res.results || []
    boothOptions.value = ['不关联展位', ...booths.value.map((b) => `${b.booth_number}（${b.location_area || '未分区'}）`)]
  } catch (err) {
    // 拉取展位失败不阻塞表单
  }
}

async function loadProduct(id: number) {
  uni.showLoading({ title: '加载中' })
  try {
    const p = (await productApi.getById(id)) as Product
    form.name = p.name || ''
    form.category = p.category || ''
    form.price = p.price !== undefined && p.price !== null ? String(p.price) : ''
    form.description = p.description || ''
    form.images = Array.isArray(p.images) ? p.images.join(',') : ''
    if (p.booth_id) {
      const idx = booths.value.findIndex((b) => b.id === p.booth_id)
      if (idx >= 0) {
        boothIndex.value = idx + 1
        form.booth_id = p.booth_id
      }
    }
    if (p.status === 'draft') statusIndex.value = 0
    else statusIndex.value = 1
  } catch (err: any) {
    uni.showToast({ title: err?.message || '加载失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

function onBoothChange(e: any) {
  boothIndex.value = Number(e.detail.value)
  const b = booths.value[boothIndex.value - 1]
  form.booth_id = b ? b.id : ''
}

function onStatusChange(e: any) {
  statusIndex.value = Number(e.detail.value)
}

function buildPayload(): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    name: form.name.trim(),
    category: form.category.trim() || undefined,
    description: form.description.trim() || undefined,
    status: statusIndex.value === 0 ? 'draft' : 'published',
  }
  if (form.booth_id) payload.booth_id = Number(form.booth_id)
  if (form.price !== '') payload.price = Number(form.price)
  const images = form.images
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter((s) => s.startsWith('http'))
  if (images.length > 0) payload.images = images
  return payload
}

async function handleSave() {
  if (!form.name.trim()) {
    uni.showToast({ title: '请输入展品名称', icon: 'none' })
    return
  }
  if (submitting.value) return
  submitting.value = true
  uni.showLoading({ title: '保存中' })
  try {
    const payload = buildPayload()
    if (editingId.value) await productApi.update(editingId.value, payload)
    else await productApi.create(payload)
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

function handleDelete() {
  if (!editingId.value) return
  uni.showModal({
    title: '提示',
    content: '确定删除该展品吗？',
    success: async ({ confirm }) => {
      if (!confirm) return
      try {
        await productApi.delete(editingId.value!)
        uni.showToast({ title: '已删除', icon: 'success' })
        setTimeout(() => uni.navigateBack(), 800)
      } catch (err: any) {
        uni.showToast({ title: err?.message || '删除失败', icon: 'none' })
      }
    },
  })
}

function goBack() {
  uni.navigateBack()
}
</script>

<template>
  <view class="page-wrapper">
    <view class="card card-body">
      <view class="form-group">
        <text class="form-label">展品名称 <text class="text-danger">*</text></text>
        <input
          v-model="form.name"
          class="form-input"
          type="text"
          placeholder="请输入展品名称"
          cursor-spacing="24"
        />
      </view>

      <view class="form-group">
        <text class="form-label">关联展位</text>
        <picker :range="boothOptions" :value="boothIndex" @change="onBoothChange">
          <view class="form-input picker-value">
            <text :class="boothIndex === 0 ? 'text-secondary' : ''">{{ boothOptions[boothIndex] }}</text>
          </view>
        </picker>
      </view>

      <view class="form-row">
        <view class="form-group form-col">
          <text class="form-label">品类</text>
          <input
            v-model="form.category"
            class="form-input"
            type="text"
            placeholder="如：电子产品"
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
        <text class="form-label">状态</text>
        <picker :range="statusOptions" :value="statusIndex" @change="onStatusChange">
          <view class="form-input picker-value">
            <text>{{ statusOptions[statusIndex] }}</text>
          </view>
        </picker>
      </view>

      <view class="form-group">
        <text class="form-label">图片URL（可选，多张用逗号分隔）</text>
        <textarea
          v-model="form.images"
          class="form-input form-textarea"
          placeholder="https://example.com/a.jpg, https://example.com/b.jpg"
          cursor-spacing="24"
        />
      </view>

      <view class="form-group">
        <text class="form-label">详细描述</text>
        <textarea
          v-model="form.description"
          class="form-input form-textarea"
          placeholder="展品规格、材质、适用场景等..."
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

      <view v-if="editingId" class="btn btn-block delete-btn mt-4" @click="handleDelete">
        删除展品
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

.delete-btn {
  background: #fff;
  color: var(--color-danger);
  border: 1px solid var(--color-border);
}
</style>
