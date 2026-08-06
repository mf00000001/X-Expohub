<script setup lang="ts">
import { useToast } from '@/composables/useToast'
const { toasts, dismiss } = useToast()
</script>
<template>
  <div class="toast-container">
    <div v-for="t in toasts" :key="t.id" :class="['toast', 'toast-' + t.type]">
      <span class="toast-icon">{{ {success:'✅',error:'❌',warning:'⚠️',info:'ℹ️'}[t.type] }}</span>
      <span class="toast-msg">{{ t.message }}</span>
      <button class="toast-close" @click="dismiss(t.id)">×</button>
    </div>
  </div>
</template>
<style scoped>
.toast-container { position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:10px }
.toast { display:flex;align-items:center;gap:10px;padding:12px 20px;border-radius:8px;min-width:280px;box-shadow:0 6px 20px rgba(0,0,0,0.1);animation:toast-in 0.3s ease;font-size:14px;background:#fff }
.toast-success { border-left:4px solid #10b981;color:#065f46 }
.toast-error { border-left:4px solid #ef4444;color:#991b1b }
.toast-warning { border-left:4px solid #f59e0b;color:#92400e }
.toast-info { border-left:4px solid #6366f1;color:#3730a3 }
.toast-icon{font-size:18px;flex-shrink:0}.toast-msg{flex:1}.toast-close{background:none;border:none;cursor:pointer;font-size:16px;opacity:.5}@keyframes toast-in{from{opacity:0;transform:translateX(100%)}to{opacity:1;transform:translateX(0)}}
</style>
