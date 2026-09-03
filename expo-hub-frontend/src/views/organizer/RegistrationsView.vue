<template>
  <div class="page-container"><div class="page-header"><h2>报名管理</h2><div>
      <button class="btn-back" @click="exportCsv()" style="margin-right:8px">⬇ 导出 CSV</button>
      <button class="btn-back" @click="$router.push('/organizer/exhibitions')">&larr; 返回列表</button>
    </div></div>
    <p v-if="exTitle" class="text-secondary text-sm" style="margin-bottom:12px">展会：{{ exTitle }}</p>
    <LoadingSkeleton v-if="loading" :lines="5"/><p v-if="error" class="error-msg">{{ error }}</p>
    <EmptyState v-if="!loading&&!error&&regs.length===0" message="暂无报名记录"/>
    <div class="table-card" v-if="regs.length>0"><table><thead><tr><th>用户</th><th>邮箱</th><th>报名码</th><th>报名时间</th><th>签到时间</th></tr></thead><tbody><tr v-for="r in regs" :key="r.id"><td>{{ r.username || ('用户#'+r.visitor_id) }}</td><td>{{ r.email || '-' }}</td><td>{{ r.ticket_code || '-' }}</td><td>{{ fmt(r.created_at) }}</td><td>{{ r.check_in_at ? fmt(r.check_in_at) : '未签到' }}</td></tr></tbody></table></div>
    <div class="pagination" v-if="total>ps"><button :disabled="p<=1" @click="p--;fetch()">上一页</button><span>第 {{ p }} / {{ tp }} 页</span><button :disabled="p>=tp" @click="p++;fetch()">下一页</button></div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'; import { useRoute } from 'vue-router'; import { registrationApi } from '@/api/registration'; import type { Registration } from '@/api/registration'; import { exhibitionApi } from '@/api/exhibition'; import LoadingSkeleton from '@/components/LoadingSkeleton.vue'; import EmptyState from '@/components/EmptyState.vue'
const route = useRoute(); const eid = Number(route.params.id); const regs = ref<Registration[]>([]); const loading = ref(false); const error = ref(''); const exTitle = ref(''); const p = ref(1); const ps = 20; const total = ref(0); const tp = computed(()=>Math.max(1,Math.ceil(total.value/ps)))
function fmt(d:string){ return d?String(d).slice(0,10):'' }
async function fetch(){ loading.value=true; error.value=''; try { const r:any = await registrationApi.getList({ page:p.value, page_size:ps, exhibition_id:eid }); regs.value=r.list||[]; total.value=r.total||0 } catch(e:any){ error.value='加载失败（仅展会的组织者或管理员可见）' } finally { loading.value=false } }
async function exportCsv() {
  try {
    const token = localStorage.getItem('access_token') || ''
    const xhr = new XMLHttpRequest()
    xhr.open('GET', '/api/registrations/export?exhibition_id=' + eid)
    xhr.setRequestHeader('Authorization', 'Bearer ' + token)
    xhr.responseType = 'blob'
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(xhr.response)
        a.download = '报名名单_展会' + eid + '.csv'
        a.click()
        URL.revokeObjectURL(a.href)
      } else {
        alert('导出失败（' + xhr.status + '）')
      }
    }
    xhr.onerror = () => alert('导出失败：网络错误')
    xhr.send()
  } catch (e) { alert('导出失败：' + String(e)) }
}
onMounted(async () => { exhibitionApi.getDetail(eid).then((e:any)=>{ exTitle.value = e?.title || '' }).catch(()=>{}); await fetch() })
</script>
<style scoped>.page-container{max-width:1200px;margin:0 auto}.filters{margin-bottom:16px}</style>
