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
    error.value = e.response?.data?.detail || 'Failed to load exhibition'
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
    success.value = 'Exhibition updated successfully!'
    setTimeout(() => {
      router.push({ name: 'organizer-exhibitions' })
    }, 1500)
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || 'Update failed'
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
        <button class="btn btn-outline btn-sm" @click="goBack">&larr; Back</button>
        <h1 class="page-title" style="margin-bottom:0">Edit Exhibition</h1>
      </div>

      <div v-if="loading" class="card p-6 text-center">Loading...</div>

      <div v-else class="card">
        <div class="card-body">
          <div v-if="success" class="tag tag-green mb-4 p-4" style="display:block;">{{ success }}</div>
          <div v-if="error" class="form-error mb-4">{{ error }}</div>

          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <label class="form-label">Exhibition Name <span class="text-danger">*</span></label>
              <input v-model="form.title" class="form-input" type="text" placeholder="Enter exhibition name" />
            </div>

            <div class="form-group">
              <label class="form-label">Description</label>
              <textarea v-model="form.description" class="form-input form-textarea" placeholder="Enter description..."></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Cover Image URL</label>
              <div v-if="form.cover_image" class="cover-preview mb-2">
                <img :src="form.cover_image" alt="preview" style="max-width:300px;max-height:150px;object-fit:cover;border-radius:8px" />
              </div>
              <input v-model="form.cover_image" class="form-input" type="text" placeholder="https://example.com/image.jpg" />
            </div>

            <div class="grid grid-cols-1 grid-cols-2 gap-4">
              <div class="form-group">
                <label class="form-label">Start Date <span class="text-danger">*</span></label>
                <input v-model="form.start_date" class="form-input" type="date" />
              </div>
              <div class="form-group">
                <label class="form-label">End Date <span class="text-danger">*</span></label>
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
              <label class="form-label">Location</label>
              <input v-model="form.location" class="form-input" type="text" placeholder="e.g. Shanghai National Exhibition Center" />
            </div>

            <div class="form-group">
              <label class="form-label">Category</label>
              <select v-model="form.category" class="form-input">
                <option value="">Select category</option>
                <option v-for="cat in EXHIBITION_CATEGORIES" :key="cat" :value="cat">{{ cat }}</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Status</label>
              <select v-model="form.status" class="form-input">
                <option value="draft">Draft</option>
                <option value="pending">Pending</option>
                <option value="active">Published</option>
              </select>
            </div>

            <div class="flex gap-2 mt-6">
              <button type="submit" class="btn btn-primary btn-lg" :disabled="submitting">
                {{ submitting ? 'Saving...' : 'Save Changes' }}
              </button>
              <button type="button" class="btn btn-outline btn-lg" @click="goBack">Cancel</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>
