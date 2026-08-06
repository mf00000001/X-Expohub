<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'
import { boothApi } from '@/api/booth'

const router = useRouter()
const submitting = ref(false)
const error = ref('')
const success = ref('')

const exhibitions = ref<Exhibition[]>([])
const exhibitionsLoading = ref(true)

const form = ref({
  exhibition_id: '' as string | number,
  booth_number: '',
  company_name: '',
  size: '',
  location_area: '',
  price: null as number | null,
  description: '',
  status: 'available',
})

async function fetchExhibitions() {
  exhibitionsLoading.value = true
  try {
    const res = await exhibitionApi.getList({ page: 1, page_size: 100 })
    exhibitions.value = res.list || res.items || res.results || []
  } catch (e: any) {
    // ignore
  } finally {
    exhibitionsLoading.value = false
  }
}

onMounted(fetchExhibitions)

async function handleSubmit() {
  error.value = ''
  success.value = ''

  if (!form.value.exhibition_id) {
    error.value = '请选择所属展会'
    return
  }
  if (!form.value.booth_number.trim()) {
    error.value = '请输入展位号'
    return
  }

  submitting.value = true
  try {
    await boothApi.create({
      exhibition_id: Number(form.value.exhibition_id),
      booth_number: form.value.booth_number.trim(),
      company_name: form.value.company_name.trim() || undefined,
      size: form.value.size.trim() || undefined,
      location_area: form.value.location_area.trim() || undefined,
      price: form.value.price ?? undefined,
      description: form.value.description.trim() || undefined,
      status: form.value.status,
    })
    success.value = '展位创建成功！'
    setTimeout(() => {
      router.push({ name: 'organizer-exhibitions' })
    }, 1500)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '创建失败，请重试'
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push({ name: 'organizer-dashboard' })
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex items-center gap-2 mb-6">
        <button class="btn btn-outline btn-sm" @click="goBack">← 返回</button>
        <h1 class="page-title" style="margin-bottom:0">创建展位</h1>
      </div>

      <div class="card">
        <div class="card-body">
          <div v-if="success" class="tag tag-green mb-4 p-4" style="display:block;">{{ success }}</div>
          <div v-if="error" class="form-error mb-4">{{ error }}</div>

          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <label class="form-label">所属展会 <span class="text-danger">*</span></label>
              <select v-model="form.exhibition_id" class="form-input">
                <option value="">请选择展会</option>
                <option v-for="ex in exhibitions" :key="ex.id" :value="ex.id">
                  {{ ex.title }}
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">展位号 <span class="text-danger">*</span></label>
              <input
                v-model="form.booth_number"
                class="form-input"
                type="text"
                placeholder="如：A-001"
              />
            </div>

            <div class="grid grid-cols-1 grid-cols-2 gap-4">
              <div class="form-group">
                <label class="form-label">面积</label>
                <input
                  v-model="form.size"
                  class="form-input"
                  type="text"
                  placeholder="如：9㎡"
                />
              </div>

              <div class="form-group">
                <label class="form-label">价格</label>
                <input
                  v-model.number="form.price"
                  class="form-input"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">所在区域</label>
              <input
                v-model="form.location_area"
                class="form-input"
                type="text"
                placeholder="如：主展厅A区"
              />
            </div>

            <div class="form-group">
              <label class="form-label">公司名称（预分配）</label>
              <input
                v-model="form.company_name"
                class="form-input"
                type="text"
                placeholder="留空表示待申请"
              />
            </div>

            <div class="form-group">
              <label class="form-label">展位描述</label>
              <textarea
                v-model="form.description"
                class="form-input form-textarea"
                placeholder="展位配置、设施等信息..."
              ></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">状态</label>
              <select v-model="form.status" class="form-input">
                <option value="available">可申请</option>
                <option value="reserved">已预定</option>
                <option value="occupied">已占用</option>
              </select>
            </div>

            <div class="flex gap-2 mt-6">
              <button type="submit" class="btn btn-primary btn-lg" :disabled="submitting">
                {{ submitting ? '创建中...' : '创建展位' }}
              </button>
              <button type="button" class="btn btn-outline btn-lg" @click="goBack">取消</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>
