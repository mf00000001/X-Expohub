<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { boothApi, type Booth } from '@/api/booth'
import { productApi, EXHIBITION_CATEGORIES } from '@/api/product'

const router = useRouter()
const submitting = ref(false)
const error = ref('')
const success = ref('')

const booths = ref<Booth[]>([])
const boothsLoading = ref(true)

const form = ref({
  booth_id: '' as string | number,
  name: '',
  description: '',
  category: '',
  price: null as number | null,
  unit: '',
  stock: null as number | null,
  images: [] as string[],
})

const newImageUrl = ref('')

async function fetchBooths() {
  boothsLoading.value = true
  try {
    const res = await boothApi.getMyBooths({ page: 1, page_size: 100 })
    booths.value = res.list || res.items || res.results || []
  } catch (e: any) {
    // ignore
  } finally {
    boothsLoading.value = false
  }
}

onMounted(fetchBooths)

function addImage() {
  const url = newImageUrl.value.trim()
  if (url && !form.value.images.includes(url)) {
    form.value.images.push(url)
    newImageUrl.value = ''
  }
}

function removeImage(index: number) {
  form.value.images.splice(index, 1)
}

async function handleSubmit() {
  error.value = ''
  success.value = ''

  if (!form.value.name.trim()) {
    error.value = '请输入展品名称'
    return
  }

  submitting.value = true
  try {
    const payload: any = {
      name: form.value.name.trim(),
      description: form.value.description.trim() || undefined,
      category: form.value.category || undefined,
      price: form.value.price ?? undefined,
      unit: form.value.unit || undefined,
      stock: form.value.stock ?? undefined,
      images: form.value.images.length > 0 ? form.value.images : undefined,
    }
    if (form.value.booth_id) {
      payload.booth_id = Number(form.value.booth_id)
    }
    await productApi.create(payload)
    success.value = '展品添加成功！'
    setTimeout(() => {
      router.push({ name: 'exhibitor-products' })
    }, 1500)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '添加失败，请重试'
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push({ name: 'exhibitor-products' })
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex items-center gap-2 mb-6">
        <button class="btn btn-outline btn-sm" @click="goBack">← 返回</button>
        <h1 class="page-title" style="margin-bottom:0">添加展品</h1>
      </div>

      <div class="card">
        <div class="card-body">
          <div v-if="success" class="tag tag-green mb-4 p-4" style="display:block;">{{ success }}</div>
          <div v-if="error" class="form-error mb-4">{{ error }}</div>

          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <label class="form-label">所属展位（可选）</label>
              <select v-model="form.booth_id" class="form-input">
                <option value="">不关联展位</option>
                <option v-for="b in booths" :key="b.id" :value="b.id">
                  {{ b.company_name || b.exhibitor_name || b.booth_number }} — {{ b.booth_number }}
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">展品名称 <span class="text-danger">*</span></label>
              <input
                v-model="form.name"
                class="form-input"
                type="text"
                placeholder="请输入展品名称"
              />
            </div>

            <div class="form-group">
              <label class="form-label">展品描述</label>
              <textarea
                v-model="form.description"
                class="form-input form-textarea"
                placeholder="请描述展品的特点、规格、用途等..."
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
                <label class="form-label">库存</label>
                <input
                  v-model.number="form.stock"
                  class="form-input"
                  type="number"
                  min="0"
                  placeholder="0"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">展品图片</label>
              <div class="flex gap-2 mb-2">
                <input
                  v-model="newImageUrl"
                  class="form-input"
                  type="text"
                  placeholder="输入图片URL"
                  @keyup.enter.prevent="addImage"
                />
                <button type="button" class="btn btn-outline btn-sm" @click="addImage">添加</button>
              </div>
              <div v-if="form.images.length > 0" class="flex gap-2 flex-wrap">
                <div v-for="(img, idx) in form.images" :key="idx" class="image-tag">
                  <span class="text-sm">{{ img.substring(0, 30) }}{{ img.length > 30 ? '...' : '' }}</span>
                  <button type="button" class="btn-remove" @click="removeImage(idx)">×</button>
                </div>
              </div>
            </div>

            <div class="flex gap-2 mt-6">
              <button type="submit" class="btn btn-primary btn-lg" :disabled="submitting">
                {{ submitting ? '添加中...' : '确认添加' }}
              </button>
              <button type="button" class="btn btn-outline btn-lg" @click="goBack">取消</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.image-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--color-bg);
  border-radius: var(--radius);
  border: 1px solid var(--color-border);
}
.btn-remove {
  background: none;
  color: var(--color-danger);
  font-size: 18px;
  line-height: 1;
  padding: 0 2px;
}
</style>
