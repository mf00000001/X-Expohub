<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { exhibitionApi } from '@/api/exhibition'
import { venueApi, type Venue } from '@/api/venue'
import { EXHIBITION_CATEGORIES } from '@/api/product'

const router = useRouter()
const route = useRoute()
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

// V3.1: 展馆选择
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
    // 选择展馆后自动填充举办地点
    form.value.location = `${v.name}（${v.address}）`
  }
}

// V3.3: 内嵌选馆对比面板(不跳转,避免表单数据丢失)
const showPicker = ref(false)
const pickerCity = ref('全部')
const pickerSort = ref<'area' | 'city'>('area')
const pickerCities = computed(() => {
  const set = new Set(venues.value.map((v) => v.city))
  return ['全部', ...Array.from(set).sort()]
})
const pickerList = computed(() => {
  let list = venues.value
  if (pickerCity.value !== '全部') {
    list = list.filter((v) => v.city === pickerCity.value)
  }
  const arr = [...list]
  if (pickerSort.value === 'area') {
    arr.sort((a, b) => (b.area || 0) - (a.area || 0))
  } else {
    arr.sort((a, b) => a.city.localeCompare(b.city, 'zh-CN'))
  }
  return arr
})
function pickVenue(v: Venue) {
  form.value.venue_id = v.id
  form.value.location = `${v.name}（${v.address}）`
  showPicker.value = false
}
function trafficHint(v: Venue): string {
  const t = v.important_info || ''
  const idx = t.indexOf('地铁')
  if (idx >= 0) {
    const seg = t.slice(idx, idx + 40)
    return seg.split(/[;；。]/)[0] || seg
  }
  const idx2 = t.indexOf('机场')
  if (idx2 >= 0) return t.slice(idx2, idx2 + 30)
  return ''
}
function currentVenueLabel(): string {
  const v = venues.value.find((x) => x.id === form.value.venue_id)
  return v ? `${v.name}（${v.city} · ${v.area ? v.area + '万㎡' : '面积待确认'}）` : ''
}
onMounted(() => {
  loadVenues()
  // V3.3: 支持从选馆页带 venue_id 跳转(自动选中并填充)
  const qid = Number(route.query.venue_id)
  if (qid) {
    form.value.venue_id = qid
    const v = venues.value.find((x) => x.id === qid)
    if (v) form.value.location = `${v.name}（${v.address}）`
  }
})

async function handleSubmit() {
  error.value = ''
  success.value = ''

  if (!form.value.title.trim()) {
    error.value = '请输入展会名称'
    return
  }
  if (!form.value.start_date) {
    error.value = '请选择开始日期'
    return
  }
  if (!form.value.end_date) {
    error.value = '请选择结束日期'
    return
  }
  if (form.value.end_date < form.value.start_date) {
    error.value = '结束日期不能早于开始日期'
    return
  }

  submitting.value = true
  try {
    await exhibitionApi.create({
      title: form.value.title.trim(),
      description: form.value.description.trim() || undefined,
      cover_image: form.value.cover_image || undefined,
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      location: form.value.location.trim() || '待定',
      category: form.value.category || undefined,
      status: 'draft',
      total_booths: Number(form.value.total_booths) || 10,
      venue_id: form.value.venue_id ?? undefined,
    })
    success.value = '展会创建成功！'
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
  router.push({ name: 'organizer-exhibitions' })
}
</script>

<template>
  <div>
        <div class="container page-wrapper">
      <div class="flex items-center gap-2 mb-6">
        <button class="btn btn-outline btn-sm" @click="goBack">← 返回</button>
        <h1 class="page-title" style="margin-bottom:0">创建展会</h1>
      </div>

      <div class="card">
        <div class="card-body">
          <div v-if="success" class="tag tag-green mb-4 p-4" style="display:block;">{{ success }}</div>
          <div v-if="error" class="form-error mb-4">{{ error }}</div>

          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <label class="form-label">展会名称 <span class="text-danger">*</span></label>
              <input
                v-model="form.title"
                class="form-input"
                type="text"
                placeholder="请输入展会名称"
              />
            </div>

            <div class="form-group">
              <label class="form-label">展会描述</label>
              <textarea
                v-model="form.description"
                class="form-input form-textarea"
                placeholder="请输入展会描述信息..."
              ></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">封面图片 URL</label>
              <div v-if="form.cover_image" class="cover-preview mb-2">
                <img :src="form.cover_image" alt="preview" style="max-width:300px;max-height:150px;object-fit:cover;border-radius:8px" @error="" />
              </div>
              <input
                v-model="form.cover_image"
                class="form-input"
                type="text"
                placeholder="https://example.com/image.jpg"
              />
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
              <label class="form-label">展馆选择 <span class="text-muted">（选填,选择后自动填充地点）</span></label>
              <div class="flex gap-2">
                <select v-model="form.venue_id" class="form-input" @change="onVenueChange">
                  <option :value="null">请选择展馆（可不选）</option>
                  <option v-for="v in venues" :key="v.id" :value="v.id">{{ v.name }}（{{ v.city }} · {{ v.area }}万㎡）</option>
                </select>
                <button type="button" class="btn btn-outline" style="white-space:nowrap" @click="showPicker = !showPicker">
                  {{ showPicker ? '收起对比' : '🔍 对比挑选' }}
                </button>
              </div>
              <div v-if="form.venue_id" class="venue-selected">✅ 已选：{{ currentVenueLabel() }}</div>
              <div v-if="venuesLoading" class="text-muted" style="font-size:12px;margin-top:4px;">展馆加载中...</div>

              <!-- 内嵌选馆对比面板 -->
              <div v-if="showPicker" class="picker-panel">
                <div class="picker-toolbar">
                  <div class="picker-chips">
                    <button v-for="c in pickerCities" :key="c" class="chip" :class="{ 'chip-active': pickerCity === c }" @click="pickerCity = c">{{ c }}</button>
                  </div>
                  <select v-model="pickerSort" class="form-input" style="width:auto">
                    <option value="area">面积从大到小</option>
                    <option value="city">按城市</option>
                  </select>
                </div>
                <div class="picker-list">
                  <div v-for="v in pickerList" :key="v.id" class="picker-row" :class="{ 'picker-row-active': form.venue_id === v.id }" @click="pickVenue(v)">
                    <div class="pr-main">
                      <div class="pr-title">
                        <span class="pr-name">{{ v.name }}</span>
                        <span class="pr-city">{{ v.city }}</span>
                      </div>
                      <div class="pr-meta">
                        <span>📐 {{ v.area ? v.area + ' 万㎡' : '面积待确认' }}</span>
                        <span v-if="trafficHint(v)">🚇 {{ trafficHint(v) }}</span>
                      </div>
                      <div class="pr-honors">
                        <span v-for="(h, i) in (v.honors || []).slice(0, 2)" :key="i" class="pr-honor">🏅 {{ h }}</span>
                      </div>
                    </div>
                    <button type="button" class="btn btn-sm" :class="form.venue_id === v.id ? 'btn-success' : 'btn-outline'" @click.stop="pickVenue(v)">{{ form.venue_id === v.id ? '已选 ✓' : '选择' }}</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">举办地点</label>
              <input
                v-model="form.location"
                class="form-input"
                type="text"
                placeholder="如：上海国家会展中心"
              />
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
                {{ submitting ? '创建中...' : '创建展会' }}
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
.venue-selected {
  margin-top: 6px; font-size: 13px; color: #15803d;
  background: #f0fdf4; border: 1px solid #bbf7d0;
  border-radius: 8px; padding: 6px 10px; display: inline-block;
}
.picker-panel {
  margin-top: 10px;
  border: 1px solid #93c5fd; border-radius: 12px;
  padding: 12px; background: #f8fafc;
  max-height: 380px; display: flex; flex-direction: column;
}
.picker-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; flex-wrap: wrap; margin-bottom: 10px;
}
.picker-chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  border: 1px solid #e2e8f0; background: #fff; border-radius: 999px;
  padding: 4px 12px; font-size: 12px; color: #475569; cursor: pointer; transition: all .2s;
}
.chip:hover { border-color: #93c5fd; color: #2563eb; }
.chip-active { background: #2563eb; border-color: #2563eb; color: #fff; font-weight: 500; }
.picker-list { overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.picker-row {
  display: flex; align-items: center; gap: 12px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 10px 12px; cursor: pointer; transition: all .2s;
}
.picker-row:hover { border-color: #93c5fd; }
.picker-row-active { border-color: #2563eb; background: #eff6ff; }
.pr-main { flex: 1; min-width: 0; }
.pr-title { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.pr-name { font-size: 14px; font-weight: 600; color: #1f2937; }
.pr-city {
  background: #eff6ff; color: #2563eb; border-radius: 5px;
  padding: 0 6px; font-size: 11px; font-weight: 600;
}
.pr-meta { display: flex; gap: 10px; font-size: 12px; color: #64748b; margin-bottom: 4px; flex-wrap: wrap; }
.pr-honors { display: flex; gap: 5px; flex-wrap: wrap; }
.pr-honor {
  font-size: 11px; color: #b45309; background: #fffbeb;
  border-radius: 5px; padding: 1px 6px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px;
}
</style>