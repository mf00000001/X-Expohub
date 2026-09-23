# 页面开发约定

新增或改写页面时遵守本约定，保证代码风格统一、能在小程序端正常跑。

## 迁移规则

### 1. 文件与结构
- 位置：`expo-hub-miniapp/src/pages/<path>.vue`
- 一个文件 = 一个页面，标准三段式 `<script setup lang="ts">` + `<template>` + `<style scoped>`
- 新增路由需同步登记到 `src/pages.json`

### 2. 允许的 import
```ts
import { ref, reactive, computed, onMounted } from 'vue'
import { onLoad, onShow, onReachBottom, onPullDownRefresh } from '@dcloudio/uni-app'
import { exhibitionApi, type Exhibition } from '@/api/exhibition'  // 各 api 模块
import ExpoCard from '@/components/ExpoCard.vue'                   // 组件显式 import
import { useUserStore } from '@/stores/user'
```
- **禁止**：axios、vue-router、`useRouter`、`window`、`document`、`localStorage`、`import.meta.env`

### 3. 标签转换（HTML → 小程序）
| HTML | 小程序 |
|---|---|
| `<div>` | `<view>` |
| `<span>` | `<text>` |
| `<img :src>` | `<image :src mode="aspectFill">`（封面类）或 `mode="aspectFit"`（产品图） |
| `<input v-model>` | `<input :value="x" @input="e=>x=e.detail.value">` 或 `v-model` |
| `<textarea>` | `<textarea :value @input>` |
| `<select>/<option>` | `<picker :range="arr" @change="e=>x=arr[e.detail.value]">` |
| `<button @click>` | `<view class="btn btn-primary" @click>`（用全局 .btn 类，不用原生 button） |
| `<a :href>` | `<view @click="uni.navigateTo...">` |

- 文案、图标 emoji 原样保留；`card`、`btn`、`form-input`、`tag`、`text-secondary`、`flex` 等全局类**已在 App.vue 定义，直接复用**
- 尺寸用 **rpx**（约 = px×2），字体也可保留 px
- 原生 `input` 必须显式给 `height`，只给 padding 会导致文字被竖向裁切

### 4. 路由（替换 vue-router）
| 旧 | 新 |
|---|---|
| `router.push({ name: 'exhibition-detail', params:{id} })` | `uni.navigateTo({ url: '/pages/exhibitions/detail?id=' + id })` |
| `router.push('/search?q=...')` | `uni.navigateTo({ url: '/pages/search/index?q=' + encodeURIComponent(q) })` |
| **tab 页**跳转（首页/展会/消息/我的） | **必须** `uni.switchTab({ url: '/pages/exhibitions/list' })` |
| 返回 | `uni.navigateBack()` |

目标页面接收参数：
```ts
onLoad((options) => {
  const id = Number(options?.id || 0)
  // 或 const q = options?.q || ''
})
```
注意：switchTab 不能带参数，跨 tab 传值用 `uni.setStorageSync('search_keyword', q)` 中转（展会列表页在 onShow 里读）。

### 5. API 用法
api 已封装好，`http.get<T>()` 直接返回解包后的 data（不要再 `.then(r=>r.data)`）：
```ts
const res = await exhibitionApi.getList({ page: 1, page_size: 10, status: 'published' })
// 注意：后端列表字段是 list（统一分页结构 { list, total, page, pageSize, totalPages }）
list.value = res.list || res.items || res.results || []
// 还有更多用 res.total > list.length 判断
```
**BASE_URL 已含 /api 前缀**，接口路径如 `/exhibitions` 直接写（见 `src/config/index.ts`）。
各模块：`authApi` / `exhibitionApi` / `boothApi` / `productApi` / `procurementApi` / `messageApi`

### 6. 错误处理
- 错误对象取 `err.message`（或 `err.detail`）
- 提示：`uni.showToast({ title: err.message || '操作失败', icon: 'none' })`
- 加载：`uni.showLoading({ title: '提交中' })` / `uni.hideLoading()`
- 确认：`uni.showModal({ title, content, success: ({confirm})=>... })`
- 后端返回结构：`{ success, code, message, data }`，token 由请求层自动注入/刷新

### 7. 登录态
- `useUserStore()`：`isLoggedIn`、`profile`、`login()`、`register()`、`logout()`、`fetchProfile()`
- 需要登录的操作直接调接口；401 时请求层会自动刷新并跳登录页，页面不用自己处理

### 8. 样式
- 每个页面 `<style scoped>` 写页面私有样式，能复用全局类就复用
- 列表页面尽量支持 `onReachBottom` 分页（page 从 1 开始，`res.total` 判断是否还有更多）

## 提交前自查

- 无 axios / vue-router / window / document / localStorage
- import 路径正确，组件显式注册
- 新增页面已登记 `src/pages.json`
- 原生 `input` 都写了 `height`
