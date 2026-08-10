# ExpoHub 展会撮合平台 — Uniapp 前端设计文档

> 版本：v1.0 | 最后更新：2025-01 | 作者：Orchestrator（基于 Frontend Agent 产出梳理）

---

## 📋 目录

1. [技术栈与架构概览](#1-技术栈与架构概览)
2. [四端路由规划（pages.json）](#2-四端路由规划pagesjson)
3. [分包策略](#3-分包策略)
4. [TabBar 配置](#4-tabbar-配置)
5. [路由守卫机制](#5-路由守卫机制)
6. [各端核心页面清单](#6-各端核心页面清单)
7. [组件规划](#7-组件规划)
8. [API 接口层设计](#8-api-接口层设计)
9. [状态管理](#9-状态管理)
10. [核心工具函数](#10-核心工具函数)
11. [文件目录结构](#11-文件目录结构)

---

## 1. 技术栈与架构概览

### 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| **框架** | UniApp (Vue 3 + Composition API) | 一套代码编译到 H5 / 微信小程序 / App |
| **语言** | TypeScript（组件/API层） + JavaScript（工具层） | 渐进式 TS 迁移策略 |
| **构建工具** | Vite | UniApp Vue3 默认构建 |
| **状态管理** | Pinia | 轻量、类型友好 |
| **CSS 预处理** | SCSS | 嵌套、变量、mixin |
| **HTTP 请求** | uni.request 二次封装 | 拦截器、自动刷新 Token、并发队列 |
| **路由守卫** | uni.addInterceptor | 页面跳转拦截 + 角色权限校验 |
| **图标方案** | Emoji + iconfont | 轻量免额外依赖 |

### 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                      页面层 (Pages)                          │
│  ├── 主包页面 (15页)                                        │
│  ├── 游客分包 (3页)                                         │
│  ├── 展商分包 (6页)                                         │
│  ├── 主办方分包 (9页)                                       │
│  └── 老板分包 (9页)                                         │
├─────────────────────────────────────────────────────────────┤
│                      组件层 (Components)                     │
│  ├── 公共组件 (12个)                                        │
│  └── 角色专属组件（按需内联）                                │
├─────────────────────────────────────────────────────────────┤
│                      API 层 (src/api/)                       │
│  ├── request.ts  —— 统一请求封装（拦截器/Token刷新）         │
│  ├── auth.ts     —— 认证接口                                │
│  ├── exhibition.ts —— 展会接口                              │
│  ├── booth.ts    —— 展位接口                                │
│  ├── procurement.js —— 采购需求接口                          │
│  └── ...                                                    │
├─────────────────────────────────────────────────────────────┤
│                    状态管理层 (src/stores/)                  │
│  ├── user.ts     —— 用户登录态/角色                          │
│  └── app.ts      —— 应用全局配置                             │
├─────────────────────────────────────────────────────────────┤
│                    工具层 (src/utils/ + src/core/)           │
│  ├── auth.js     —— Token管理/角色首页路径                   │
│  ├── role.js     —— 角色权限映射/路由守卫                    │
│  ├── request.js  —— JS版请求封装                            │
│  ├── router.js   —— 路由守卫（旧版）                        │
│  └── format.js   —— 日期/金额格式化                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 四端路由规划（pages.json）

### 2.1 完整路由配置

> 📄 配置文件：`expo-hub-uniapp/src/pages.json`

#### 主包页面（pages）

主包包含**所有角色共享的公共页面**，确保首次加载即可访问核心功能：

| 路由路径 | 页面标题 | 自定义导航栏 | 下拉刷新 | 触底加载 |
|---------|---------|:---------:|:------:|:------:|
| `pages/index/index` | ExpoHub 展会通 | ✅ custom | ✅ | - |
| `pages/exhibition/list` | 展会列表 | - | ✅ | ✅ 50px |
| `pages/exhibition/detail` | 展会详情 | ✅ custom | - | - |
| `pages/booth/detail` | 展位详情 | - | - | - |
| `pages/product/list` | 展品列表 | - | ✅ | - |
| `pages/product/detail` | 展品详情 | - | - | - |
| `pages/procurement/list` | 采购需求 | - | ✅ | - |
| `pages/procurement/detail` | 采购需求详情 | - | - | - |
| `pages/message/list` | 消息中心 | - | - | - |
| `pages/message/conversation` | 会话详情 | - | - | - |
| `pages/user/login` | 登录 | ✅ custom | - | - |
| `pages/user/register` | 注册 | ✅ custom | - | - |
| `pages/user/profile` | 个人主页 | ✅ custom | - | - |
| `pages/user/settings` | 设置 | - | - | - |
| `pages/search/index` | 搜索 | ✅ custom | - | - |

#### 设计说明

- **主包 15 页**：控制在合理范围，保证首屏加载速度
- **custom 导航栏**：首页、展会详情、登录/注册、个人主页、搜索页使用自定义导航栏，便于沉浸式体验和品牌露出
- **下拉刷新**：列表类页面（展会列表、展品列表、采购需求）启用
- **触底加载**：展会列表设置 `onReachBottomDistance: 50` 实现无限滚动

---

### 2.2 分包详细配置

#### 游客分包（pages_visitor）

```json
{
  "root": "pages_visitor",
  "pages": [
    { "path": "my_registrations",  "title": "我的报名/收藏" },
    { "path": "my_procurements",   "title": "我的采购需求" },
    { "path": "procurement_create", "title": "发布采购需求" }
  ]
}
```

| 页面 | 功能 | 权限 |
|------|------|------|
| `my_registrations` | 查看已报名展会、已收藏展会，可取消报名/收藏 | visitor |
| `my_procurements` | 查看已发布的采购需求列表，查看匹配状态 | visitor |
| `procurement_create` | 发布新的采购需求（标题/品类/预算/数量/描述） | visitor |

#### 展商分包（pages_exhibitor）

```json
{
  "root": "pages_exhibitor",
  "pages": [
    { "path": "dashboard",          "title": "展商工作台", "custom": true },
    { "path": "my_booths",          "title": "我的展位" },
    { "path": "my_products",        "title": "我的展品" },
    { "path": "product_create",     "title": "添加展品" },
    { "path": "product_edit",       "title": "编辑展品" },
    { "path": "procurement_matches","title": "采购匹配" }
  ]
}
```

| 页面 | 功能 | 权限 |
|------|------|------|
| `dashboard` | 展商工作台：今日数据概览、快捷入口、待处理事项 | exhibitor |
| `my_booths` | 我的展位列表：已预订展位、展位状态、所属展会 | exhibitor |
| `my_products` | 展品管理列表：支持上下架、编辑、删除 | exhibitor |
| `product_create` | 添加新展品（名称/品类/价格/图片/描述） | exhibitor |
| `product_edit` | 编辑已有展品信息 | exhibitor |
| `procurement_matches` | 采购需求匹配大厅：浏览游客发布的采购需求、响应匹配 | exhibitor |

#### 主办方分包（pages_organizer）

```json
{
  "root": "pages_organizer",
  "pages": [
    { "path": "dashboard",        "title": "主办方工作台", "custom": true },
    { "path": "exhibition_list",  "title": "我的展会", "pullRefresh": true },
    { "path": "exhibition_create","title": "创建展会" },
    { "path": "exhibition_edit",  "title": "编辑展会" },
    { "path": "booth_layout",     "title": "展位布局" },
    { "path": "booth_create",     "title": "创建展位" },
    { "path": "booth_assign",     "title": "分配展位" },
    { "path": "registrations",    "title": "报名管理" },
    { "path": "statistics",       "title": "数据统计" }
  ]
}
```

| 页面 | 功能 | 权限 |
|------|------|------|
| `dashboard` | 主办方工作台：旗下展会概览、关键指标、快捷操作 | organizer |
| `exhibition_list` | 展会管理列表：创建的所有展会、状态管理（草稿/已发布/已结束） | organizer |
| `exhibition_create` | 创建新展会：名称、时间、地点、展馆、描述、封面 | organizer |
| `exhibition_edit` | 编辑已有展会信息 | organizer |
| `booth_layout` | 展位布局图管理：可视化展区规划 | organizer |
| `booth_create` | 创建展位：编号、区域、面积、价格 | organizer |
| `booth_assign` | 分配展位给已审核通过的展商 | organizer |
| `registrations` | 报名管理：查看所有报名记录、导出名单 | organizer |
| `statistics` | 数据统计：展会维度数据（浏览量/报名数/展商数/成交额） | organizer |

#### 老板分包（pages_boss）

```json
{
  "root": "pages_boss",
  "pages": [
    { "path": "dashboard",         "title": "老板驾驶舱", "custom": true },
    { "path": "stats_overview",    "title": "全局概览" },
    { "path": "stats_users",       "title": "用户分析" },
    { "path": "stats_exhibitions", "title": "展会分析" },
    { "path": "approval_list",     "title": "待审批列表" },
    { "path": "approval_detail",   "title": "审批详情" },
    { "path": "team_list",         "title": "团队列表" },
    { "path": "team_create",       "title": "创建团队" },
    { "path": "team_members",      "title": "成员管理" }
  ]
}
```

| 页面 | 功能 | 权限 |
|------|------|------|
| `dashboard` | 老板驾驶舱：全局核心指标一览（用户数/展会数/成交额/活跃度） | boss |
| `stats_overview` | 全局数据概览：多维度图表（趋势/分布/排行） | boss |
| `stats_users` | 用户分析：注册趋势、角色分布、活跃度 | boss |
| `stats_exhibitions` | 展会分析：展会数量趋势、地域分布、热门排行 | boss |
| `approval_list` | 待审批列表：展会发布审批、展商资质审批 | boss |
| `approval_detail` | 审批详情：查看申请详情并做出审批决定 | boss |
| `team_list` | 团队列表：管理的所有团队 | boss |
| `team_create` | 创建新团队 | boss |
| `team_members` | 成员管理：添加/移除成员、角色分配 | boss |

---

## 3. 分包策略

### 3.1 分包原则

```
主包 (main package)
├── 核心公共页面（首页/展会列表/详情/搜索/消息/登录/个人中心）
├── 体积控制在 ~2MB 以内
└── 所有角色首次访问必须的页面
    ↓
分包 (subPackages)
├── pages_visitor    —— 游客专属页面（3页）
├── pages_exhibitor  —— 展商专属页面（6页）
├── pages_organizer  —— 主办方专属页面（9页）
└── pages_boss       —— 老板专属页面（9页）
```

### 3.2 预加载策略

```json
{
  "preloadRule": {
    "pages/index/index": {
      "network": "all",
      "packages": ["pages_visitor", "pages_exhibitor"]
    },
    "pages_organizer/dashboard": {
      "network": "all",
      "packages": ["pages_organizer"]
    },
    "pages_boss/dashboard": {
      "network": "all",
      "packages": ["pages_boss"]
    }
  }
}
```

| 触发页面 | 预加载分包 | 说明 |
|---------|-----------|------|
| 首页 | 游客 + 展商 | 首页是游客和展商的主要入口，登录后预加载对应分包 |
| 主办方工作台 | 主办方 | 登录为主办方后立即预加载 |
| 老板驾驶舱 | 老板 | 登录为老板后立即预加载 |

### 3.3 分包体积估算

| 分包 | 页面数 | 预估体积 | 说明 |
|------|:-----:|---------|------|
| 主包 | 15 | ~800KB | 公共页面 + 核心组件 |
| pages_visitor | 3 | ~60KB | 轻量分包 |
| pages_exhibitor | 6 | ~120KB | 含展品编辑表单 |
| pages_organizer | 9 | ~200KB | 含展会创建/展位布局 |
| pages_boss | 9 | ~180KB | 含图表/审批页面 |

> 小程序限制：主包 ≤ 2MB，总包 ≤ 20MB（微信），当前方案完全满足。

---

## 4. TabBar 配置

```json
{
  "tabBar": {
    "color": "#999999",
    "selectedColor": "#3B82F6",
    "backgroundColor": "#ffffff",
    "borderStyle": "black",
    "list": [
      {
        "pagePath": "pages/index/index",
        "iconPath": "static/icons/tab_home.png",
        "selectedIconPath": "static/icons/tab_home_active.png",
        "text": "首页"
      },
      {
        "pagePath": "pages/exhibition/list",
        "iconPath": "static/icons/tab_exhibition.png",
        "selectedIconPath": "static/icons/tab_exhibition_active.png",
        "text": "展会"
      },
      {
        "pagePath": "pages/message/list",
        "iconPath": "static/icons/tab_message.png",
        "selectedIconPath": "static/icons/tab_message_active.png",
        "text": "消息"
      },
      {
        "pagePath": "pages/user/profile",
        "iconPath": "static/icons/tab_profile.png",
        "selectedIconPath": "static/icons/tab_profile_active.png",
        "text": "我的"
      }
    ]
  }
}
```

### TabBar 设计理念

| Tab | 图标 | 定位 | 适用角色 |
|-----|------|------|---------|
| **首页** | 🏠 | 角色差异化首页：游客看推荐展会、展商看工作台入口、主办方/老板快捷跳转 | 全部 |
| **展会** | 📋 | 展会列表：支持筛选（时间/城市/状态）、搜索 | 全部 |
| **消息** | 💬 | 消息中心：IM 会话列表、系统通知、未读红点 | 全部（需登录） |
| **我的** | 👤 | 个人中心：角色信息、设置、角色专属入口 | 全部 |

### TabBar 动态切换方案（可选增强）

对于展商/主办方/老板角色，TabBar 可动态替换"我的"为对应工作台入口：

```typescript
// 按角色动态设置 TabBar
function setTabBarByRole(role: string) {
  const tabBarMap = {
    visitor:    { text: '我的',   pagePath: 'pages/user/profile' },
    exhibitor:  { text: '工作台', pagePath: 'pages_exhibitor/dashboard' },
    organizer:  { text: '管理',   pagePath: 'pages_organizer/dashboard' },
    boss:       { text: '驾驶舱', pagePath: 'pages_boss/dashboard' },
  }
  // 使用 uni.setTabBarItem 动态修改
}
```

---

## 5. 路由守卫机制

### 5.1 架构设计

```
用户跳转页面
    │
    ▼
uni.addInterceptor ('navigateTo' / 'switchTab' / 'reLaunch' / 'redirectTo')
    │
    ▼
checkRoute(url)
    │
    ├── ① 检查是否需要登录
    │   ├── 需要 & 未登录 → 跳转登录页 ❌
    │   └── 不需要 / 已登录 → 继续
    │
    ├── ② 检查角色权限
    │   ├── 有权访问 → 放行 ✅
    │   └── 无权访问 → Toast提示 + 跳转角色首页 ❌
    │
    └── ③ 登录后导航
        └── navigateAfterLogin(role) → 跳转对应角色首页
```

### 5.2 角色-路由权限映射表

> 📄 实现文件：`expo-hub-uniapp/src/utils/role.js`

```javascript
const ROUTE_ROLE_MAP = {
  // ===== 公共页面 =====
  'pages/index/index':             ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/exhibition/list':         ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/exhibition/detail':       ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/booth/detail':            ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/product/list':            ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/product/detail':          ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/procurement/list':        ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/procurement/detail':      ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/message/list':            ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/message/conversation':    ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/user/profile':            ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/user/settings':           ['visitor', 'exhibitor', 'organizer', 'boss'],
  'pages/search/index':            ['visitor', 'exhibitor', 'organizer', 'boss'],

  // ===== 公开页面（未登录可访问）=====
  'pages/user/login':              ['*'],
  'pages/user/register':           ['*'],

  // ===== 游客专属 =====
  'pages_visitor/my_registrations':   ['visitor'],
  'pages_visitor/my_procurements':    ['visitor'],
  'pages_visitor/procurement_create': ['visitor'],

  // ===== 展商专属 =====
  'pages_exhibitor/dashboard':          ['exhibitor'],
  'pages_exhibitor/my_booths':          ['exhibitor'],
  'pages_exhibitor/my_products':        ['exhibitor'],
  'pages_exhibitor/product_create':     ['exhibitor'],
  'pages_exhibitor/product_edit':       ['exhibitor'],
  'pages_exhibitor/procurement_matches':['exhibitor'],

  // ===== 主办方专属 =====
  'pages_organizer/dashboard':        ['organizer'],
  'pages_organizer/exhibition_list':  ['organizer'],
  'pages_organizer/exhibition_create':['organizer'],
  'pages_organizer/exhibition_edit':  ['organizer'],
  'pages_organizer/booth_layout':     ['organizer'],
  'pages_organizer/booth_create':     ['organizer'],
  'pages_organizer/booth_assign':     ['organizer'],
  'pages_organizer/registrations':    ['organizer'],
  'pages_organizer/statistics':       ['organizer'],

  // ===== 老板专属 =====
  'pages_boss/dashboard':          ['boss'],
  'pages_boss/stats_overview':     ['boss'],
  'pages_boss/stats_users':        ['boss'],
  'pages_boss/stats_exhibitions':  ['boss'],
  'pages_boss/approval_list':      ['boss'],
  'pages_boss/approval_detail':    ['boss'],
  'pages_boss/team_list':          ['boss'],
  'pages_boss/team_create':        ['boss'],
  'pages_boss/team_members':       ['boss'],
}
```

### 5.3 路由守卫核心函数

| 函数 | 说明 |
|------|------|
| `normalizePath(path)` | 路径标准化：去 `/`、去参数 |
| `isPageRequireAuth(path)` | 判断页面是否需要登录 |
| `checkRoleAccess(path, role)` | 检查角色是否有权访问 |
| `getAccessibleRoutes(role)` | 获取某角色所有可访问路由 |
| `checkRoute(url)` | 路由检查入口，返回 boolean |
| `setupRouteGuard()` | 安装拦截器（H5 端 uni.addInterceptor） |
| `navigateAfterLogin(role)` | 登录后跳转角色首页 |

### 5.4 角色首页路径映射

```javascript
const rolePaths = {
  visitor:   '/pages/index/index',                          // 游客 → 首页
  exhibitor: '/pages/index/index',                          // 展商 → 首页（TabBar）
  organizer: '/pages_organizer/dashboard',                   // 主办方 → 工作台
  boss:      '/pages_boss/dashboard',                       // 老板 → 驾驶舱
}
```

---

## 6. 各端核心页面清单

### 6.1 游客端（3 个专属页 + 13 个公共页）

```
游客端页面地图
├── 🏠 首页 (pages/index/index)              ← 推荐展会/快捷入口
├── 📋 展会列表 (pages/exhibition/list)       ← 筛选/搜索展会
├── 📄 展会详情 (pages/exhibition/detail)     ← 展会信息/展商列表/展位图
├── 🏢 展位详情 (pages/booth/detail)          ← 展位信息/展品
├── 📦 展品列表 (pages/product/list)          ← 浏览展品
├── 📦 展品详情 (pages/product/detail)        ← 展品详情
├── 📝 采购需求列表 (pages/procurement/list)  ← 浏览采购需求
├── 📝 采购需求详情 (pages/procurement/detail)
├── 🔍 搜索 (pages/search/index)             ← 全局搜索
├── 💬 消息列表 (pages/message/list)          ← 会话列表
├── 💬 会话详情 (pages/message/conversation)  ← IM聊天
├── 👤 个人主页 (pages/user/profile)          ← 角色信息/入口
├── ⚙️ 设置 (pages/user/settings)            ← 账号设置
├── 🔐 登录 (pages/user/login)
├── 📝 注册 (pages/user/register)
│
└── 游客专属 ─────────────────────────────
    ├── 📌 我的报名/收藏 (pages_visitor/my_registrations)
    ├── 📋 我的采购需求 (pages_visitor/my_procurements)
    └── ➕ 发布采购需求 (pages_visitor/procurement_create)
```

**核心用户流程**：
1. **浏览展会**：首页 → 展会列表 → 展会详情 → 报名/收藏
2. **搜索展商**：搜索 → 展商详情 → 展品列表
3. **发布采购**：采购需求列表 → 发布采购需求 → 等待匹配 → 查看匹配

### 6.2 展商端（6 个专属页 + 13 个公共页）

```
展商端页面地图
├── 公共页面（同上13个）
│
└── 展商专属 ─────────────────────────────
    ├── 📊 展商工作台 (pages_exhibitor/dashboard)
    │     └── 今日数据概览/快捷入口/待处理事项
    ├── 🏢 我的展位 (pages_exhibitor/my_booths)
    │     └── 已预订展位列表/展位状态
    ├── 📦 我的展品 (pages_exhibitor/my_products)
    │     └── 展品管理/上下架/删除
    ├── ➕ 添加展品 (pages_exhibitor/product_create)
    ├── ✏️ 编辑展品 (pages_exhibitor/product_edit)
    └── 🎯 采购匹配 (pages_exhibitor/procurement_matches)
          └── 浏览采购需求/响应匹配/报价
```

**核心用户流程**：
1. **管理展品**：工作台 → 我的展品 → 添加/编辑展品
2. **查看需求**：工作台 → 采购匹配 → 筛选需求 → 响应匹配
3. **管理展位**：工作台 → 我的展位 → 查看展位详情

### 6.3 主办方端（9 个专属页 + 13 个公共页）

```
主办方端页面地图
├── 公共页面（同上13个）
│
└── 主办方专属 ───────────────────────────
    ├── 📊 主办方工作台 (pages_organizer/dashboard)
    │     └── 旗下展会概览/关键指标/快捷操作
    ├── 📋 我的展会 (pages_organizer/exhibition_list)
    │     └── 展会管理列表/状态管理
    ├── ➕ 创建展会 (pages_organizer/exhibition_create)
    ├── ✏️ 编辑展会 (pages_organizer/exhibition_edit)
    ├── 🗺️ 展位布局 (pages_organizer/booth_layout)
    │     └── 可视化展区规划
    ├── ➕ 创建展位 (pages_organizer/booth_create)
    ├── 📌 分配展位 (pages_organizer/booth_assign)
    │     └── 将展位分配给已审核展商
    ├── 📝 报名管理 (pages_organizer/registrations)
    │     └── 报名记录/导出名单
    └── 📈 数据统计 (pages_organizer/statistics)
          └── 展会维度数据/图表
```

**核心用户流程**：
1. **展会管理**：工作台 → 我的展会 → 创建/编辑展会 → 发布
2. **展位规划**：展会详情 → 展位布局 → 创建展位 → 分配展商
3. **审核管理**：工作台 → 报名管理 → 查看报名 → 展商审核

### 6.4 老板端（9 个专属页 + 13 个公共页）

```
老板端页面地图
├── 公共页面（同上13个）
│
└── 老板专属 ─────────────────────────────
    ├── 📊 老板驾驶舱 (pages_boss/dashboard)
    │     └── 全局核心指标一览
    ├── 📈 全局概览 (pages_boss/stats_overview)
    │     └── 多维度图表（趋势/分布/排行）
    ├── 👥 用户分析 (pages_boss/stats_users)
    │     └── 注册趋势/角色分布/活跃度
    ├── 🏢 展会分析 (pages_boss/stats_exhibitions)
    │     └── 数量趋势/地域分布/热门排行
    ├── ✅ 待审批列表 (pages_boss/approval_list)
    │     └── 展会发布审批/展商资质审批
    ├── 📄 审批详情 (pages_boss/approval_detail)
    ├── 👥 团队列表 (pages_boss/team_list)
    ├── ➕ 创建团队 (pages_boss/team_create)
    └── 👤 成员管理 (pages_boss/team_members)
          └── 添加/移除成员/角色分配
```

**核心用户流程**：
1. **数据查看**：驾驶舱 → 全局概览/用户分析/展会分析
2. **审批管理**：待审批列表 → 审批详情 → 通过/驳回
3. **团队管理**：团队列表 → 创建团队 → 成员管理

---

## 7. 组件规划

### 7.1 组件总览

```
src/components/
├── 展示类 (4个)
│   ├── ExpoCard.vue          ← 展会卡片（封面/标题/日期/地点/状态）
│   ├── ExhibitorCard.vue     ← 展商卡片（Logo/名称/行业/展位号）
│   ├── ProductCard.vue       ← 展品卡片（图片/名称/价格/分类）
│   └── ProcurementCard.vue   ← 采购需求卡片（标题/品类/预算/状态）
│
├── 数据类 (2个)
│   ├── StatsCard.vue         ← 统计卡片（数值/标签/图标/趋势）
│   └── StatusTag.vue         ← 状态标签（多状态/颜色/尺寸）
│
├── 导航类 (2个)
│   ├── NavBar.vue            ← 自定义导航栏（标题/返回/透明渐变/插槽）
│   └── SearchBar.vue         ← 搜索栏（防抖/清除/筛选按钮）
│
├── 容器类 (3个)
│   ├── ExpoList.vue          ← 展会列表容器（下拉刷新/触底加载/空状态）
│   ├── EmptyState.vue        ← 空状态占位（图标/文案/操作按钮）
│   └── LoadingSkeleton.vue   ← 骨架屏加载（脉冲动画/多布局）
│
└── 权限类 (1个)
    └── RoleGuard.vue         ← 角色守卫组件（按角色显示/隐藏内容）
```

### 7.2 公共组件详解

#### ExpoCard（展会卡片）

```typescript
Props:
  title: string            // 展会名称
  subtitle?: string        // 副标题（如：场馆名称）
  coverUrl?: string        // 封面图 URL
  status?: string          // 状态：draft/published/ongoing/ended
  icon?: string            // 无图时显示的 emoji 图标
  extra?: string           // 底部额外信息
  infoItems?: InfoItem[]   // 信息行：[{label, value}, ...]
  to?: string              // 点击跳转路径
  query?: Record<string, any> // 跳转参数

Slots:
  info    // 自定义信息区域
  footer  // 自定义底部区域
```

**使用场景**：首页推荐展会、展会列表、搜索结果

#### ExhibitorCard（展商卡片）

```typescript
Props:
  logo: string             // 展商 Logo
  name: string             // 公司名称
  industry?: string        // 行业分类
  boothNumber?: string     // 展位号
  status?: string          // 审核状态
  to?: string              // 点击跳转

Slots:
  tags     // 标签插槽
  actions  // 操作按钮插槽
```

**使用场景**：展会详情展商列表、展商搜索、展商审核列表

#### ProductCard（展品卡片）

```typescript
Props:
  image: string            // 展品图片
  name: string             // 展品名称
  category?: string        // 品类
  price?: number           // 价格
  isOnSale?: boolean       // 是否上架
  to?: string              // 点击跳转
```

**使用场景**：展品列表、展位详情、展商详情

#### ProcurementCard（采购需求卡片）

```typescript
Props:
  title: string            // 需求标题
  category: string         // 品类
  budget?: string          // 预算范围
  quantity?: number        // 采购数量
  status: string           // 状态：open/matched/completed/closed
  deadline?: string        // 截止日期
  matchCount?: number      // 匹配数
  to?: string              // 点击跳转
```

**使用场景**：采购需求列表、采购匹配大厅、我的采购需求

#### StatsCard（统计卡片）

```typescript
Props:
  value: number | string   // 数值（自动千分位格式化）
  label: string            // 标签文本
  icon?: string            // emoji 图标
  color?: 'blue' | 'green' | 'orange' | 'purple'  // 左侧色条颜色
  trend?: string           // 趋势：+5%、-2%
```

**使用场景**：展商工作台、主办方工作台、老板驾驶舱、统计页面

#### StatusTag（状态标签）

```typescript
Props:
  status: string           // 状态值
  size?: 'sm' | 'md' | 'lg'
  // 内置状态映射：
  //   draft → 灰色"草稿"
  //   published → 蓝色"已发布"
  //   ongoing → 绿色"进行中"
  //   ended → 灰色"已结束"
  //   pending → 橙色"待审核"
  //   approved → 绿色"已通过"
  //   rejected → 红色"已驳回"
  //   open → 蓝色"开放中"
  //   matched → 绿色"已匹配"
  //   completed → 灰色"已完成"
```

**使用场景**：几乎所有卡片和详情页面的状态展示

#### NavBar（自定义导航栏）

```typescript
Props:
  title?: string           // 标题
  showBack?: boolean       // 是否显示返回按钮
  backgroundColor?: string // 背景色
  transparent?: boolean    // 是否透明渐变（滚动时变实色）
  backIcon?: string        // 返回图标

Slots:
  right   // 右侧操作区插槽

Events:
  back    // 返回按钮点击
```

**使用场景**：所有 `navigationStyle: custom` 的页面

#### SearchBar（搜索栏）

```typescript
Props:
  placeholder?: string     // 占位文本
  modelValue?: string      // v-model 绑定
  showFilter?: boolean     // 是否显示筛选按钮
  debounce?: number        // 防抖延迟 (ms)
  backgroundColor?: string // 背景色

Events:
  search        // 搜索触发（防抖后）
  filter-click  // 筛选按钮点击
```

**使用场景**：展会列表、展商搜索、采购需求搜索

#### ExpoList（展会列表容器）

```typescript
Props:
  exhibitions: Exhibition[]  // 展会数据
  loading?: boolean          // 加载状态
  hasMore?: boolean          // 是否有更多
  emptyText?: string         // 空状态文案

Events:
  refresh       // 下拉刷新
  loadMore      // 触底加载
  itemClick     // 点击展会
```

**使用场景**：首页推荐、展会列表

#### EmptyState（空状态占位）

```typescript
Props:
  icon?: string            // 图标
  text?: string            // 提示文案
  showAction?: boolean     // 是否显示操作按钮
  actionText?: string      // 按钮文案

Slots:
  action   // 自定义操作区
```

**使用场景**：空列表、无搜索结果、无消息

#### LoadingSkeleton（骨架屏）

```typescript
Props:
  type?: 'card' | 'list' | 'detail'  // 骨架类型
  count?: number                      // 重复数量
```

**使用场景**：列表首次加载、详情页加载

#### RoleGuard（角色守卫组件）

```typescript
Props:
  roles: string[]          // 允许的角色列表
  requireAuth?: boolean    // 是否需要登录
  fallback?: boolean       // 无权限时是否显示占位
  fallbackText?: string    // 无权限提示文案

Slots:
  default   // 有权限时展示的内容
  fallback  // 无权限时展示的占位内容
```

**使用场景**：页面中根据角色条件渲染特定模块

### 7.3 角色专属组件（建议）

以下组件尚未独立抽取，建议后续按需从页面中提取：

| 组件名 | 所属角色 | 说明 |
|--------|:------:|------|
| `BoothMap.vue` | organizer | 展位布局可视化组件（拖拽/缩放/标注） |
| `ChartDashboard.vue` | boss | 图表仪表盘容器（封装 echarts/ucharts） |
| `ApprovalActions.vue` | boss | 审批操作栏（通过/驳回/备注） |
| `ProcurementForm.vue` | visitor | 采购需求表单（品类选择/预算滑块） |
| `ProductForm.vue` | exhibitor | 展品信息表单（图片上传/分类选择） |
| `IMChat.vue` | 通用 | IM 聊天核心组件（消息列表/输入框） |
| `TeamMemberItem.vue` | boss | 团队成员列表项（角色标签/操作菜单） |
| `BoothCard.vue` | exhibitor/organizer | 展位卡片（编号/面积/价格/状态） |

---

## 8. API 接口层设计

### 8.1 请求封装架构

```
src/api/request.ts
├── 基础配置
│   ├── BASE_URL: /api/v1
│   └── REQUEST_TIMEOUT: 15000ms
│
├── 拦截器链
│   ├── 请求前：自动附加 Authorization Bearer Token
│   ├── 响应：统一解析 ApiResponse<T>
│   ├── 401：自动刷新 Token（并发请求排队）
│   └── 刷新失败：清除登录态 → 跳转登录页
│
├── 导出方法
│   ├── http.get<T>(url, config)
│   ├── http.post<T>(url, data, config)
│   ├── http.put<T>(url, data, config)
│   ├── http.delete<T>(url, config)
│   ├── http.patch<T>(url, data, config)
│   └── http.upload<T>(url, filePath, name, formData)
│
└── Token 刷新机制
    ├── refreshPromise：防止并发刷新
    ├── pendingQueue：刷新期间请求排队
    └── 刷新成功后批量重放
```

### 8.2 API 模块清单

| 文件 | 对应 Service | 主要接口 |
|------|-------------|---------|
| `src/api/auth.ts` | AuthService | register / login / refresh / logout / me |
| `src/api/exhibition.ts` | ExhibitionService | list / detail / create / update / publish |
| `src/api/booth.ts` | BoothService | list / create / update / book / assign |
| `src/api/procurement.js` | ProcurementService | list / create / detail / match / accept |
| `src/api/request.ts` | 基础层 | 统一请求封装 |

### 8.3 统一响应格式

```typescript
interface ApiResponse<T> {
  code: number        // 200 成功 / 401 未授权 / 403 无权限 / 422 参数错误
  message: string     // 提示信息
  data: T             // 业务数据
}

interface PaginatedResponse<T> {
  items: T[]          // 数据列表
  total: number       // 总条数
  page: number        // 当前页
  page_size: number   // 每页条数
  total_pages: number // 总页数
}
```

---

## 9. 状态管理

### 9.1 Store 模块

#### UserStore（`src/stores/user.ts`）

```typescript
interface UserState {
  token: string | null         // Access Token
  refreshToken: string | null  // Refresh Token
  userId: number | null
  username: string
  role: string                 // visitor | exhibitor | organizer | boss
  isLoggedIn: boolean          // 计算属性
}

// Actions
setTokens(accessToken, refreshToken)  // 存储令牌
setUserInfo(userInfo)                 // 存储用户信息
logout()                              // 清除登录态
fetchUserProfile()                    // 获取用户信息
```

#### AppStore（`src/store/app.js`）

```typescript
interface AppState {
  systemInfo: object        // 系统信息（状态栏高度等）
  networkStatus: string     // 网络状态
  unreadCount: number       // 未读消息数
}
```

---

## 10. 核心工具函数

### 10.1 auth.js — 认证管理

| 函数 | 说明 |
|------|------|
| `saveTokens(accessToken, refreshToken)` | 存储到 Storage |
| `getTokens()` | 读取 Token |
| `clearTokens()` | 清除 Token |
| `saveUserInfo(userInfo)` | 存储用户信息 |
| `getUserInfo()` | 读取用户信息 |
| `clearUserInfo()` | 清除用户信息 |
| `isLoggedIn()` | 判断登录状态 |
| `getRoleHomePath(role)` | 获取角色首页路径 |
| `getRoleName(role)` | 获取角色中文名 |

### 10.2 role.js — 角色权限

| 函数 | 说明 |
|------|------|
| `isPageRequireAuth(path)` | 页面是否需要登录 |
| `checkRoleAccess(path, role)` | 角色是否有权访问 |
| `getAccessibleRoutes(role)` | 获取角色可访问路由列表 |
| `checkRoute(url)` | 路由检查 |
| `setupRouteGuard()` | 安装路由守卫 |
| `navigateAfterLogin(role)` | 登录后导航 |

### 10.3 format.js — 格式化工具

| 函数 | 说明 |
|------|------|
| `formatDate(date, format)` | 日期格式化 |
| `formatPrice(price)` | 价格格式化（千分位+¥符号） |
| `formatNumber(num)` | 数字千分位 |
| `relativeTime(date)` | 相对时间（3分钟前/昨天） |
| `truncateText(text, len)` | 文本截断+省略号 |

---

## 11. 文件目录结构

```
expo-hub-uniapp/
│
├── App.vue                          # 应用入口（路由守卫安装）
├── main.js                          # 旧版入口
├── manifest.json                    # UniApp 配置（旧版）
├── pages.json                       # 旧版路由配置
├── uni.scss                         # 旧版全局样式
│
├── src/                             # 核心源码目录 ★
│   ├── App.vue                      # 应用入口
│   ├── main.ts                      # 入口（Pinia 安装）
│   ├── manifest.json                # UniApp 配置
│   ├── pages.json                   # ★ 路由配置（主包 + 4个分包）
│   ├── uni.scss                     # 全局 SCSS 变量
│   │
│   ├── pages/                       # ★ 主包页面（15页）
│   │   ├── index/index.vue          # 首页
│   │   ├── exhibition/
│   │   │   ├── list.vue             # 展会列表
│   │   │   └── detail.vue           # 展会详情
│   │   ├── booth/detail.vue         # 展位详情
│   │   ├── product/
│   │   │   ├── list.vue             # 展品列表
│   │   │   └── detail.vue           # 展品详情
│   │   ├── procurement/
│   │   │   ├── list.vue             # 采购需求列表
│   │   │   └── detail.vue           # 采购需求详情
│   │   ├── message/
│   │   │   ├── list.vue             # 消息列表
│   │   │   └── conversation.vue     # 会话详情
│   │   ├── user/
│   │   │   ├── login.vue            # 登录
│   │   │   ├── register.vue         # 注册
│   │   │   ├── profile.vue          # 个人主页
│   │   │   └── settings.vue         # 设置
│   │   └── search/index.vue         # 全局搜索
│   │
│   ├── pages_visitor/               # ★ 游客分包（3页）
│   │   ├── my_registrations.vue
│   │   ├── my_procurements.vue
│   │   └── procurement_create.vue
│   │
│   ├── pages_exhibitor/             # ★ 展商分包（6页）
│   │   ├── dashboard.vue
│   │   ├── my_booths.vue
│   │   ├── my_products.vue
│   │   ├── product_create.vue
│   │   ├── product_edit.vue
│   │   └── procurement_matches.vue
│   │
│   ├── pages_organizer/             # ★ 主办方分包（9页）
│   │   ├── dashboard.vue
│   │   ├── exhibition_list.vue
│   │   ├── exhibition_create.vue
│   │   ├── exhibition_edit.vue
│   │   ├── booth_layout.vue
│   │   ├── booth_create.vue
│   │   ├── booth_assign.vue
│   │   ├── registrations.vue
│   │   └── statistics.vue
│   │
│   ├── pages_boss/                  # ★ 老板分包（9页）
│   │   ├── dashboard.vue
│   │   ├── stats_overview.vue
│   │   ├── stats_users.vue
│   │   ├── stats_exhibitions.vue
│   │   ├── approval_list.vue
│   │   ├── approval_detail.vue
│   │   ├── team_list.vue
│   │   ├── team_create.vue
│   │   └── team_members.vue
│   │
│   ├── components/                  # ★ 公共组件（12个）
│   │   ├── ExpoCard.vue             # 展会卡片
│   │   ├── ExhibitorCard.vue        # 展商卡片
│   │   ├── ProductCard.vue          # 展品卡片
│   │   ├── ProcurementCard.vue      # 采购需求卡片
│   │   ├── StatsCard.vue            # 统计卡片
│   │   ├── StatusTag.vue            # 状态标签
│   │   ├── NavBar.vue               # 自定义导航栏
│   │   ├── SearchBar.vue            # 搜索栏
│   │   ├── ExpoList.vue             # 展会列表容器
│   │   ├── EmptyState.vue           # 空状态
│   │   ├── LoadingSkeleton.vue      # 骨架屏
│   │   └── RoleGuard.vue            # 角色守卫
│   │
│   ├── api/                         # ★ API 接口层
│   │   ├── request.ts               # 统一请求封装（TS版）
│   │   ├── request.js               # 统一请求封装（JS版）
│   │   ├── auth.ts                  # 认证接口
│   │   ├── exhibition.ts            # 展会接口
│   │   ├── exhibition.js            # 展会接口（JS版）
│   │   ├── booth.ts                 # 展位接口
│   │   ├── procurement.js           # 采购需求接口
│   │   └── auth.js                  # 认证接口（JS版）
│   │
│   ├── stores/                      # ★ Pinia 状态管理
│   │   └── user.ts                  # 用户状态
│   │
│   ├── store/                       # 旧版 Vuex（待迁移）
│   │   ├── index.js
│   │   ├── app.js
│   │   └── user.js
│   │
│   ├── core/                        # ★ 核心工具
│   │   ├── auth.js                  # Token管理/角色路由
│   │   ├── request.js               # 请求封装
│   │   └── router.js                # 路由守卫（旧版）
│   │
│   └── utils/                       # ★ 工具函数
│       ├── auth.js                  # 认证工具
│       ├── role.js                  # ★ 角色权限+路由守卫
│       └── format.js                # 格式化工具
│
├── static/                          # 静态资源
│   └── icons/                       # TabBar 图标
│       ├── tab_home.png
│       ├── tab_home_active.png
│       ├── tab_exhibition.png
│       ├── tab_exhibition_active.png
│       ├── tab_message.png
│       ├── tab_message_active.png
│       ├── tab_profile.png
│       └── tab_profile_active.png
│
└── docs/                            # 文档
    └── expo-hub-uniapp-frontend-design.md  # ★ 本文档
```

---

## 附录 A：全局样式变量（uni.scss）

```scss
// 主题色
$primary-color: #3B82F6;
$primary-light: #EFF6FF;
$primary-dark: #1D4ED8;

// 功能色
$success-color: #10B981;
$warning-color: #F59E0B;
$danger-color: #EF4444;
$info-color: #6366F1;

// 中性色
$text-primary: #1F2937;
$text-secondary: #6B7280;
$text-hint: #9CA3AF;
$border-color: #E5E7EB;
$bg-color: #F5F5F5;
$bg-white: #FFFFFF;

// 圆角
$radius-sm: 8rpx;
$radius-md: 16rpx;
$radius-lg: 24rpx;
$radius-full: 9999rpx;

// 阴影
$shadow-sm: 0 2rpx 8rpx rgba(0, 0, 0, 0.06);
$shadow-md: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);

// 间距
$spacing-xs: 8rpx;
$spacing-sm: 16rpx;
$spacing-md: 24rpx;
$spacing-lg: 32rpx;
$spacing-xl: 48rpx;
```

---

## 附录 B：待优化事项

| 优先级 | 事项 | 说明 |
|:------:|------|------|
| P1 | **JS → TS 迁移** | store/ 目录下的 Vuex → Pinia TS 迁移；api/ 下 JS 文件统一为 TS |
| P1 | **IM 聊天组件化** | 将 message/conversation.vue 中的聊天 UI 抽取为独立的 IMChat 组件 |
| P1 | **图表组件集成** | 老板端/主办方端统计页面接入 uCharts 或 ECharts |
| P2 | **TabBar 动态切换** | 按角色动态替换 TabBar 的"我的"为工作台 |
| P2 | **小程序分包优化** | 将公共组件按需打入分包，减少主包体积 |
| P2 | **暗黑模式支持** | 基于 uni.scss 变量扩展暗黑主题 |
| P3 | **国际化 i18n** | 预留 vue-i18n 接入点 |
| P3 | **单元测试** | 组件 + 工具函数的 Vitest 测试覆盖 |

---

> 📌 **文档说明**：本文档基于 Frontend Agent 已完成的代码产出进行梳理总结，涵盖 ExpoHub Uniapp 前端的完整设计方案。后端架构请参阅 `docs/expo-hub-architecture.md`。
