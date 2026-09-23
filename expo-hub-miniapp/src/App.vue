<script>
import { useUserStore } from '@/stores/user'

export default {
  onLaunch() {
    // 启动时静默恢复登录态（本地已有 token 时拉取一次资料）
    const token = uni.getStorageSync('access_token')
    if (token) {
      // 延迟到进入首页后再拉取，避免启动竞态
      setTimeout(() => {
        const store = useUserStore()
        store.fetchProfile().catch(() => {
          // token 失效交给请求层 401 逻辑处理，这里静默
        })
      }, 300)
    }
  },
}
</script>

<style>
/* ===== 全局主题变量 ===== */
:root,
page {
  --color-primary: #3b82f6;
  --color-primary-hover: #2563eb;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-info: #6366f1;
  --color-bg: #f5f7fa;
  --color-white: #ffffff;
  --color-text: #1f2937;
  --color-text-secondary: #6b7280;
  --color-border: #e5e7eb;
  --color-card: #ffffff;
  --radius: 8px;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow: 0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05);
}

page {
  background-color: #f5f7fa;
  color: #1f2937;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue',
    Arial, 'PingFang SC', 'Noto Sans SC', sans-serif;
  font-size: 14px;
  line-height: 1.6;
  box-sizing: border-box;
}

/* ===== 布局 ===== */
.container {
  padding: 0 16px;
}

.page-wrapper {
  padding: 16px;
}

.flex {
  display: flex;
}
.flex-col {
  flex-direction: column;
}
.items-center {
  align-items: center;
}
.items-end {
  align-items: flex-end;
}
.justify-between {
  justify-content: space-between;
}
.justify-center {
  justify-content: center;
}
.flex-1 {
  flex: 1;
}
.gap-2 {
  gap: 8px;
}
.gap-3 {
  gap: 12px;
}
.gap-4 {
  gap: 16px;
}
.gap-6 {
  gap: 24px;
}
.flex-wrap {
  flex-wrap: wrap;
}

/* ===== 按钮 ===== */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 20px;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 500;
  gap: 6px;
  box-sizing: border-box;
}
.btn-primary {
  background-color: var(--color-primary);
  color: #fff;
}
.btn-success {
  background-color: var(--color-success);
  color: #fff;
}
.btn-danger {
  background-color: var(--color-danger);
  color: #fff;
}
.btn-outline {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text);
}
.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}
.btn-lg {
  padding: 12px 28px;
  font-size: 16px;
}
.btn-block {
  width: 100%;
}
.btn-disabled {
  opacity: 0.6;
}

/* ===== 卡片 ===== */
.card {
  background: var(--color-card);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--color-border);
  overflow: hidden;
}
.card-body {
  padding: 16px;
}
.card-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
}

/* ===== 表单 ===== */
.form-group {
  margin-bottom: 16px;
}
.form-label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
}
.form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 14px;
  background: var(--color-white);
  box-sizing: border-box;
}
.form-input:focus {
  border-color: var(--color-primary);
}
/* 原生 input 必须显式给高度。
   微信小程序的 input 是原生控件封装，WXSS 无法控制其内部行高与内边距，
   只写纵向 padding 会把文字挤出可视区（表现为占位符/文字被裁切）。
   故：纵向 padding 归零 + 显式 height/min-height，垂直居中交给原生控件。
   注意：<view class="form-input picker-value"> 那类伪输入框自带 min-height:44px，
   用 input.form-input 标签选择器可避免波及它们。 */
input.form-input {
  height: 44px;
  min-height: 44px;
  padding: 0 14px;
}
.form-textarea {
  min-height: 100px;
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: 14px;
  background: var(--color-white);
  box-sizing: border-box;
}
.form-error {
  color: var(--color-danger);
  font-size: 12px;
  margin-top: 4px;
}

/* ===== 文本 ===== */
.text-center {
  text-align: center;
}
.text-sm {
  font-size: 13px;
}
.text-lg {
  font-size: 18px;
}
.text-xl {
  font-size: 22px;
}
.text-2xl {
  font-size: 28px;
}
.font-bold {
  font-weight: 700;
}
.font-semibold {
  font-weight: 600;
}
.text-secondary {
  color: var(--color-text-secondary);
}
.text-danger {
  color: var(--color-danger);
}
.text-success {
  color: var(--color-success);
}
.text-primary {
  color: var(--color-primary);
}

/* ===== 间距 ===== */
.mt-2 {
  margin-top: 8px;
}
.mt-3 {
  margin-top: 12px;
}
.mt-4 {
  margin-top: 16px;
}
.mt-6 {
  margin-top: 24px;
}
.mb-2 {
  margin-bottom: 8px;
}
.mb-4 {
  margin-bottom: 16px;
}
.mb-6 {
  margin-bottom: 24px;
}
.p-4 {
  padding: 16px;
}
.p-6 {
  padding: 24px;
}

/* ===== 页面标题 ===== */
.page-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 20px;
  color: var(--color-text);
}

/* ===== 加载 ===== */
.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
}
.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ===== 标签 ===== */
.tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
}
.tag-blue {
  background: #dbeafe;
  color: #1d4ed8;
}
.tag-green {
  background: #d1fae5;
  color: #065f46;
}
.tag-yellow {
  background: #fef3c7;
  color: #92400e;
}
.tag-red {
  background: #fee2e2;
  color: #991b1b;
}
.tag-gray {
  background: #f3f4f6;
  color: #374151;
}

/* ===== 分隔线 ===== */
.divider {
  height: 1px;
  background: var(--color-border);
  margin: 16px 0;
}

/* ===== 空状态 ===== */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}
.empty-state-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}
.empty-state-text {
  color: var(--color-text-secondary);
  font-size: 15px;
}

/* ===== 富文本/段落 ===== */
.text-muted {
  color: var(--color-text-secondary);
}
.ellipsis {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.line-clamp-2 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.line-clamp-3 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
</style>
