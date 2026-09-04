<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import { productApi, EXHIBITION_CATEGORIES } from '@/api/product'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notOwner = ref(false)

const form = ref({
  name: '',
  description: '',
  category: '',
  status: 'draft',
  images: [] as string[],
})

const newImageUrl = ref('')
const productId = Number(route.params.id)

async function loadProduct() {
  loading.value = true
  error.value = ''
  try {
    const p: any = await productApi.getDetail(productId)
    // 仅创建者本人可编辑（后端同样拦截）
    if (p.exhibitor_id !== undefined && userStore.isLoggedIn &&
        Number(p.exhibitor_id) !== Number(userStore.profile?.id) &&
        userStore.profile?.role !== 'admin') {
      notOwner.value = true
      return
    }
    form.value.name = p.name || ''
    form.value.description = p.description || ''
    form.value.category = p.category || ''
    form.value.status = p.status || 'draft'
    form.value.images = Array.isArray(p.images) ? p.images : []
  } catch (e: any) {
    if (e?.response?.status === 404) {
      error.value = '展品不存在或已被删除'
    } else {
      error.value = e?.response?.data?.message || e?.response?.data?.detail || '加载展品失败'
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadProduct)

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
  if (!form.value.name.trim()) {
    error.value = '请输入展品名称'
    return
  }
  saving.value = true
  try {
    const payload: any = {
      name: form.value.name.trim(),
      description: form.value.description.trim() || undefined,
      category: form.value.category || undefined,
      status: form.value.status || undefined,
      images: form.value.images.length > 0 ? form.value.images : undefined,
    }
    await productApi.update(productId, payload)
    alert('✅ 展品已更新')
    router.push({ name: 'exhibitor-products' })
  } catch (e: any) {
    error.value = e?.response?.data?.message || e?.response?.data?.detail || e?.message || '保存失败，请重试'
  } finally {
    saving.value = false
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
        <h1 class="page-title" style="margin-bottom:0">编辑展品</h1>
      </div>

      <LoadingSkeleton v-if="loading" :lines="6" />

      <div v-else-if="notOwner" class="card p-6 text-center">
        <p class="text-secondary">无权编辑他人展品</p>
        <button class="btn btn-primary mt-4" @click="goBack">返回我的展品</button>
      </div>

      <div v-else-if="error && !form.name" class="card p-6 text-center">
        <p class="text-danger">{{ error }}</p>
        <button class="btn btn-primary mt-4" @click="loadProduct">重试</button>
      </div>

      <div v-else class="card">
        <div class="card-body">
          <div v-if="error" class="form-error mb-4">{{ error }}</div>

          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <label class="form-label">展品名称 <span class="text-danger">*</span></label>
              <input v-model="form.name" class="form-input" type="text" placeholder="请输入展品名称" />
            </div>

            <div class="form-group">
              <label class="form-label">展品描述</label>
              <textarea v-model="form.description" class="form-input form-textarea" rows="4" placeholder="请描述展品的特点、规格、用途等..."></textarea>
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
                <label class="form-label">状态</label>
                <select v-model="form.status" class="form-input">
                  <option value="published">已上架（公开可见）</option>
                  <option value="draft">草稿（暂不展示）</option>
                  <option value="inactive">下架</option>
                </select>
              </div>
            </div>

            <p class="form-hint" style="margin-bottom:16px">💬 平台按询盘撮合设计：报价详情不公开展示，买家将通过站内消息询价</p>

            <div class="form-group">
              <label class="form-label">展品图片（URL）</label>
              <div class="flex gap-2">
                <input v-model="newImageUrl" class="form-input" type="text" placeholder="粘贴图片 URL 后点击添加" @keyup.enter.prevent="addImage" />
                <button type="button" class="btn btn-outline" @click="addImage">+ 添加</button>
              </div>
              <div v-if="form.images.length > 0" class="image-list mt-2">
                <div v-for="(img, i) in form.images" :key="i" class="image-item">
                  <img :src="img" alt="preview" class="image-thumb" />
                  <span class="image-url">{{ img }}</span>
                  <button type="button" class="btn btn-sm btn-danger" @click="removeImage(i)">移除</button>
                </div>
              </div>
              <p v-else class="form-hint">未添加图片时将显示占位图</p>
            </div>

            <div class="flex gap-2 mt-4">
              <button class="btn btn-primary" type="submit" :disabled="saving">
                {{ saving ? '保存中...' : '💾 保存修改' }}
              </button>
              <button class="btn btn-outline" type="button" @click="goBack">取消</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.image-list { display: flex; flex-direction: column; gap: 8px; }
.image-item { display: flex; align-items: center; gap: 10px; padding: 6px 10px; background: var(--bg-page, #f8fafc); border-radius: 8px; }
.image-thumb { width: 44px; height: 44px; border-radius: 6px; object-fit: cover; flex: none; background: #e2e8f0; }
.image-url { flex: 1; font-size: 12px; color: var(--text-secondary, #64748b); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.form-hint { font-size: 12px; color: var(--text-placeholder, #94a3b8); margin-top: 4px; }
</style>
