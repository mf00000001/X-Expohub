import { ref } from 'vue'

interface Toast { id: number; type: 'success' | 'error' | 'warning' | 'info'; message: string }

const toasts = ref<Toast[]>([])
let nextId = 1

export function useToast() {
  function add(type: Toast['type'], message: string) {
    const id = nextId++
    toasts.value.push({ id, type, message })
    setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, 4000)
  }
  return {
    toasts,
    success: (msg: string) => add('success', msg),
    error: (msg: string) => add('error', msg),
    warning: (msg: string) => add('warning', msg),
    info: (msg: string) => add('info', msg),
    dismiss: (id: number) => { toasts.value = toasts.value.filter(t => t.id !== id) },
  }
}
