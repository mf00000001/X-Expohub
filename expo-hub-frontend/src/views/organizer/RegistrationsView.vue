<template>
  <div class="page-container"><div class="page-header"><h2>报名管理</h2><button class="btn-back" @click="$router.push('/organizer/exhibitions')">&larr; 返回列表</button></div>
    <LoadingSkeleton v-if="loading" :lines="5"/><p v-if="error" class="error-msg">{{ error }}</p>
    <div class="filters" v-if="!loading"><select v-model="sf" class="form-select" style="width:auto" @change="fetch"><option value="">全部状态</option><option value="pending">待审核</option><option value="approved">已通过</option><option value="rejected">已拒绝</option><option value="cancelled">已取消</option></select></div>
    <EmptyState v-if="!loading&&!error&&regs.length===0" message="暂无报名记录"/>
    <div class="table-card" v-if="regs.length>0"><table><thead><tr><th>展会</th><th>用户</th><th>联系方式</th><th>公司</th><th>展位</th><th>状态</th><th>时间</th><th>操作</th></tr></thead><tbody><tr v-for="r in regs" :key="r.id"><td>{{ r.exhibition_title||'-' }}</td><td>{{ r.user_name||'用户#'+r.user_id }}</td><td><div v-if="r.user_email">{{ r.user_email }}</div><div v-if="r.user_phone" class="text-muted">{{ r.user_phone }}</div></td><td>{{ r.company||'-' }}</td><td>{{ r.booth_number||'-' }}</td><td><StatusTag :status="r.status"/></td><td>{{ fmt(r.created_at) }}</td><td><div class="action-btns" v-if="r.status==='pending'"><button class="btn btn-sm btn-success" @click="update(r,'approved')">通过</button><button class="btn btn-sm btn-danger" @click="update(r,'rejected')">拒绝</button></div><span v-else class="text-muted">--</span></td></tr></tbody></table></div>
    <div class="pagination" v-if="total>ps"><button :disabled="p<=1" @click="p--;fetch()">上一页</button><span>第 {{ p }} / {{ tp }} 页</span><button :disabled="p>=tp" @click="p++;fetch()">下一页</button></div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'; import { useRoute } from 'vue-router'; import { registrationApi } from '@/api/registration'; import type { Registration } from '@/api/registration'; import StatusTag from '@/components/StatusTag.vue'; import LoadingSkeleton from '@/components/LoadingSkeleton.vue'; import EmptyState from '@/components/EmptyState.vue'; import { useToast } from '@/composables/useToast'
const route = useRoute(); const toast = useToast(); const eid = Number(route.params.id); const regs = ref<Registration[]>([]); const loading = ref(false); const error = ref(''); const sf = ref(''); const p = ref(1); const ps = 20; const total = ref(0); const tp = computed(()=>Math.max(1,Math.ceil(total.value/ps)))
function fmt(d:string){ return d?d.slice(0,10):'' }
async function fetch(){ loading.value=true; error.value=''; try { const pm:any={ page:p.value, page_size:ps, exhibition_id:eid }; if(sf.value)pm.status=sf.value; const r:any=await registrationApi.getList(pm); regs.value=r.list||(Array.isArray(r)?r:[]); total.value=r.total||0 } catch(e:any){ error.value='加载失败' } finally { loading.value=false } }
async function update(reg:Registration,s:string){ const a=s==='approved'?'通过':'拒绝'; if(!confirm('确定要'+a+'该报名申请吗？'))return; try { await registrationApi.updateStatus(reg.id,{status:s,notes:''}); toast.success('已'+a); await fetch() } catch(e:any){ toast.error('操作失败') } }
onMounted(fetch)
</script>
<style scoped>.page-container{max-width:1200px;margin:0 auto}.filters{margin-bottom:16px}</style>
