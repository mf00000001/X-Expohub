<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { exhibitionApi } from '@/api/exhibition'
import { venueApi, type Venue } from '@/api/venue'
import { EXHIBITION_CATEGORIES } from '@/api/product'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const success = ref('')

const form = ref({
  title: '',
  description: '',
  cover_image: '',
  start_date: '',
  end_date: '',
  location: '',
  category: '',
  status: 'draft',
  venue_id: null as number | null,
})

// V3.2: 展馆选择
const venues = ref<Venue[]>([])
const venuesLoading = ref(false)
async function loadVenues() {
  venuesLoading.value = true
  try {
    const res = await venueApi.getList()
    venues.value = res.list || []
  } catch {
    venues.value = []
  } finally {
    venuesLoading.value = false
  }
}
function onVenueChange() {
  const v = venues.value.find((x) => x.id === form.value.venue_id)
  if (v) {
    form.value.location = `${v.name}（${v.address}）`
  }
}

async function fetchExhibition() {
  loading.value = true
  error.value = ''
  try {
    const data: any = await exhibitionApi.getDetail(id)
    form.value = {
      title: data.title || '',
      description: data.description || '',
      cover_image: data.cover_image || data.cover_image_url || '',
      start_date: (data.start_date || '').slice(0, 10),
      end_date: (data.end_date || '').slice(0, 10),
      location: data.location || '',
      category: data.category || '',
      status: data.status || 'draft',
      venue_id: data.venue_info?.id || null,
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || '加载展会失败'
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  error.value = ''
  success.value = ''
  submitting.value = true
  try {
    await exhibitionApi.update(id, {
      title: form.value.title.trim(),
      description: form.value.description.trim() || undefined,
      cover_image: form.value.cover_image || undefined,
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      location: form.value.location.trim(),
      category: form.value.category || undefined,
      status: form.value.status,
      venue_id: form.value.venue_id ?? undefined,
    })
    success.value = '展会更新成功！'
    setTimeout(() => {
      router.push({ name: 'organizer-exhibitions' })
    }, 1500)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '更新失败，请重试'
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push({ name: 'organizer-exhibitions' })
}

onMounted(fetchExhibition)
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex items-center gap-2 mb-6">
        <button class="btn btn-outline btn-sm" @click="goBack">← 返回</button>
        <h1 class="page-title" style="margin-bottom:0">编辑展会</h1>
      </div>

      <div v-if="loading" class="card p-6 text-center">加载中...</div>

      <div v-else class="card">
        <div class="card-body">
          <div v-if="success" class="tag tag-green mb-4 p-4" style="display:block;">{{ success }}</div>
          <div v-if="error" class="form-error mb-4">{{ error }}</div>

          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <label class="form-label">展会名称 <span class="text-danger">*</span></label>
              <input v-model="form.title" class="form-input" type="text" placeholder="请输入展会名称" />
            </div>

            <div class="form-group">
              <label class="form-label">展会描述</label>
              <textarea v-model="form.description" class="form-input form-textarea" placeholder="请输入展会描述信息..."></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">封面图片 URL</label>
              <div v-if="form.cover_image" class="cover-preview mb-2">
                <img :src="form.cover_image" alt="preview" style="max-width:300px;max-height:150px;object-fit:cover;border-radius:8px" />
              </div>
              <input v-model="form.cover_image" class="form-input" type="text" placeholder="https://example.com/image.jpg" />
            </div>

            <div class="grid grid-cols-1 grid-cols-2 gap-4">
              <div class="form-group">
                <label class="form-label">开始日期 <span class="text-danger">*</span></label>
                <input v-model="form.start_date" class="form-input" type="date" />
              </div>
              <div class="form-group">
                <label class="form-label">结束日期 <span class="text-danger">*</span></label>
                <input v-model="form.end_date" class="form-input" type="date" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">展馆选择 <span class="text-muted">（选择后自动填充地点）</span></label>
              <select v-model="form.venue_id" class="form-input" @change="onVenueChange">
                <option :value="null">请选择展馆（可不选）</option>
                <option v-for="v in venues" :key="v.id" :value="v.id">{{ v.name }}（{{ v.city }} · {{ v.area }}万㎡）</option>
              </select>
              <div v-if="venuesLoading" class="text-muted" style="font-size:12px;margin-top:4px;">展馆加载中...</div>
            </div>

            <div class="form-group">
              <label class="form-label">举办地点</label>
              <input v-model="form.location" class="form-input" type="text" placeholder="如：上海国家会展中心" />
            </div>

            <div class="form-group">
              <label class="form-label">展会品类</label>
              <select v-model="form.category" class="form-input">
                <option value="">请选择品类</option>
                <option v-for="cat in EXHIBITION_CATEGORIES" :key="cat" :value="cat">{{ cat }}</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">状态</label>
              <select v-model="form.status" class="form-input">
                <option value="draft">草稿</option>
                <option value="pending">待审批</option>
                <option value="active">发布</option>
              </select>
            </div>

            <div class="flex gap-2 mt-6">
              <button type="submit" class="btn btn-primary btn-lg" :disabled="submitting">
                {{ submitting ? '保存中...' : '保存修改' }}
              </button>
              <button type="button" class="btn btn-outline btn-lg" @click="goBack">取消</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>
