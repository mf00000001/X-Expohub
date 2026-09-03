<script setup lang="ts">
// 展馆管理（管理员）：场馆 CRUD——后端 /api/venues GET/POST/PUT/DELETE 已具备
import { ref, onMounted } from 'vue'
import { venueApi, type Venue } from '@/api/venue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'

const venues = ref<Venue[]>([])
const loading = ref(true)
const message = ref('')
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = ref({
  name: '', city: '', address: '', area: '' as string,
  plan_image: '', image_url: '', important_info: '',
})

async function load() {
  loading.value = true
  try {
    const res: any = await venueApi.getList({ page_size: 100 })
    venues.value = res?.list || res?.items || []
  } catch (e: any) {
    message.value = e?.response?.data?.message || '加载失败'
  } finally { loading.value = false }
}

function startEdit(v: Venue) {
  editingId.value = v.id
  form.value = {
    name: v.name || '', city: v.city || '', address: v.address || '',
    area: v.area ? String(v.area) : '', plan_image: v.plan_image || '',
    image_url: v.image_url || '', important_info: v.important_info || '',
  }
}
function resetForm() {
  editingId.value = null
  form.value = { name: '', city: '', address: '', area: '', plan_image: '', image_url: '', important_info: '' }
}

async function save() {
  message.value = ''
  if (!form.value.name.trim() || !form.value.city.trim() || !form.value.address.trim()) {
    message.value = '请填写名称、城市与地址'
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      city: form.value.city.trim(),
      address: form.value.address.trim(),
      area: form.value.area ? parseFloat(form.value.area) : undefined,
      plan_image: form.value.plan_image.trim() || undefined,
      image_url: form.value.image_url.trim() || undefined,
      important_info: form.value.important_info.trim() || undefined,
    }
    if (editingId.value) await venueApi.update(editingId.value, payload)
    else await venueApi.create(payload)
    message.value = '保存成功'
    resetForm()
    await load()
  } catch (e: any) {
    message.value = e?.response?.data?.message || '保存失败'
  } finally { saving.value = false }
}

async function remove(v: Venue) {
  if (!confirm(`确定删除展馆「${v.name}」？关联展会将失去场馆信息`)) return
  try {
    await venueApi.remove(v.id)
    await load()
  } catch (e: any) {
    alert(e?.response?.data?.message || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="container page-wrapper">
    <h2>🏛️ 展馆管理</h2>
    <p class="text-secondary text-sm">主办方创建展会时可选择这些展馆（当前 {{ venues.length }} 个）</p>

    <p v-if="message" :class="message.includes('成功') ? 'tag tag-success' : 'form-error'">{{ message }}</p>

    <div class="card card-body mb-4">
      <h3>{{ editingId ? '编辑展馆' : '新增展馆' }}</h3>
      <div class="grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px">
        <input v-model="form.name" class="form-input" placeholder="展馆名称 *" />
        <input v-model="form.city" class="form-input" placeholder="城市 *" />
        <input v-model="form.address" class="form-input" placeholder="地址 *" />
        <input v-model.number="form.area" class="form-input" type="number" placeholder="面积(㎡)" />
        <input v-model="form.image_url" class="form-input" placeholder="实景图 URL" />
        <input v-model="form.plan_image" class="form-input" placeholder="平面图 URL" />
      </div>
      <input v-model="form.important_info" class="form-input mt-2" placeholder="重要信息（如层高/承重/交通）" />
      <div class="mt-3">
        <button class="btn btn-primary" :disabled="saving" @click="save">{{ saving ? '保存中...' : '保存' }}</button>
        <button v-if="editingId" class="btn btn-outline ml-sm" @click="resetForm">取消编辑</button>
      </div>
    </div>

    <LoadingSkeleton v-if="loading" :lines="4" />
    <div v-else class="venue-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px">
      <div v-for="v in venues" :key="v.id" class="card">
        <img v-if="v.image_url" :src="v.image_url" alt="" style="width:100%;height:120px;object-fit:cover;border-radius:8px" />
        <div v-else style="height:120px;background:#f0f2f5;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#aaa">无实景图</div>
        <h3 style="margin:10px 0 4px">{{ v.name }}</h3>
        <p class="text-sm text-secondary m-0">📍 {{ v.city }} · {{ v.address }}</p>
        <p class="text-sm text-secondary m-0" v-if="v.area">面积 {{ v.area }}㎡</p>
        <div class="mt-2">
          <button class="btn btn-sm btn-outline" @click="startEdit(v)">编辑</button>
          <button class="btn btn-sm btn-danger" style="margin-left:6px" @click="remove(v)">删除</button>
        </div>
      </div>
    </div>
    <EmptyState v-if="!loading && venues.length===0" message="还没有展馆，先添加一个" />
  </div>
</template>
