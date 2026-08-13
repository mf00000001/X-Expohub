<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { procurementApi } from '@/api/procurement'
import { EXHIBITION_CATEGORIES } from '@/api/product'

const router = useRouter()
const submitting = ref(false)
const error = ref('')
const success = ref('')

const exhibitions = ref<Exhibition[]>([])
const exhibitionsLoading = ref(true)

const form = ref({
  exhibition_id: '' as string | number,
  title: '',
  description: '',
  category: '',
  quantity: 1,
  unit: '',
  budget: null as number | null,
  deadline: '',
})

async function fetchExhibitions() {
  exhibitionsLoading.value = true
  try {
    const res = await exhibitionApi.getList({ page: 1, page_size: 100, status: 'active' })
    exhibitions.value = (res as any).list || (res as any).items || (res as any).results || []
  } catch (e: any) {
    // ignore — just won't show exhibitions
  } finally {
    exhibitionsLoading.value = false
  }
}

onMounted(fetchExhibitions)

async function handleSubmit() {
  error.value = ''
  success.value = ''

  if (!form.value.title.trim()) {
    error.value = '请输入采购标题'
    return
  }
  if (!form.value.description.trim()) {
    error.value = '请输入采购描述'
    return
  }

  submitting.value = true
  try {
    const payload: any = {
      title: form.value.title.trim(),
      description: form.value.description.trim(),
      category: form.value.category || undefined,
      quantity: form.value.quantity || undefined,
      unit: form.value.unit || undefined,
      budget: form.value.budget || undefined,
      deadline: form.value.deadline || undefined,
    }
    if (form.value.exhibition_id) {
      payload.exhibition_id = Number(form.value.exhibition_id)
    }
    await procurementApi.create(payload)
    success.value = '采购需求发布成功！'
    setTimeout(() => {
      router.push({ name: 'visitor-procurements' })
    }, 1500)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '发布失败，请重试'
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push({ name: 'visitor-procurements' })
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex items-center gap-2 mb-6">
        <button class="btn btn-outline btn-sm" @click="goBack">← 返回</button>
        <h1 class="page-title" style="margin-bottom:0">发布采购需求</h1>
      </div>

      <div class="card">
        <div class="card-body">
          <div v-if="success" class="tag tag-green mb-4 p-4" style="display:block;">{{ success }}</div>
          <div v-if="error" class="form-error mb-4">{{ error }}</div>

          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <label class="form-label">关联展会（可选）</label>
              <select v-model="form.exhibition_id" class="form-input">
                <option value="">不关联展会</option>
                <option v-for="ex in exhibitions" :key="ex.id" :value="ex.id">
                  {{ ex.title }}
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">采购标题 <span class="text-danger">*</span></label>
              <input
                v-model="form.title"
                class="form-input"
                type="text"
                placeholder="例如：需要采购100台智能传感器"
              />
            </div>

            <div class="form-group">
              <label class="form-label">详细描述 <span class="text-danger">*</span></label>
              <textarea
                v-model="form.description"
                class="form-input form-textarea"
                placeholder="请详细描述您需要的产品规格、要求等..."
              ></textarea>
            </div>

            <div class="grid grid-cols-1 grid-cols-2 gap-4">
              <div class="form-group">
                <label class="form-label">品类</label>
                <select v-model="form.category" class="form-input">
                  <option value="">请选择品类</option>
                  <option v-for="cat in EXHIBITION_CATEGORIES" :key="cat" :value="cat">{{ cat }}</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">数量</label>
                <input
                  v-model.number="form.quantity"
                  class="form-input"
                  type="number"
                  min="1"
                />
              </div>

              <div class="form-group">
                <label class="form-label">单位</label>
                <input
                  v-model="form.unit"
                  class="form-input"
                  type="text"
                  placeholder="如：台、件、套..."
                />
              </div>

              <div class="form-group">
                <label class="form-label">预算金额</label>
                <input
                  v-model.number="form.budget"
                  class="form-input"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">截止日期</label>
              <input v-model="form.deadline" class="form-input" type="date" />
            </div>

            <div class="flex gap-2 mt-6">
              <button type="submit" class="btn btn-primary btn-lg" :disabled="submitting">
                {{ submitting ? '发布中...' : '立即发布' }}
              </button>
              <button type="button" class="btn btn-outline btn-lg" @click="goBack">取消</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>
