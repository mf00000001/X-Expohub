import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { isLoggedIn } from '@/utils/auth'
import { getRoleHomePath } from '@/utils/auth'

const routes: RouteRecordRaw[] = [
  // ==================== 公开路由 ====================
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue'), meta: { title: '首页', requiresAuth: false, showFooter: true } },
  { path: '/login', name: 'login', component: () => import('@/views/user/LoginView.vue'), meta: { title: '登录', requiresAuth: false, roles: [], showFooter: false } },
  { path: '/register', name: 'register', component: () => import('@/views/user/RegisterView.vue'), meta: { title: '注册', requiresAuth: false, roles: [], showFooter: false } },
  { path: '/onboarding', name: 'onboarding', component: () => import('@/views/OnboardingView.vue'), meta: { title: '选择兴趣领域', requiresAuth: true, showFooter: false } },
  { path: '/exhibitions', name: 'exhibition-list', component: () => import('@/views/exhibition/ExhibitionListView.vue'), meta: { title: '展会列表', requiresAuth: false, showFooter: true } },
  { path: '/exhibitions/:id', name: 'exhibition-detail', component: () => import('@/views/exhibition/ExhibitionDetailView.vue'), meta: { title: '展会详情', requiresAuth: false, showFooter: true } },
  // 展会评估（画像层）：回答"这个展值不值得去"，与 /exhibitions 的"有哪些展"是两件事
  { path: '/expo-intel', name: 'expo-intel', component: () => import('@/views/persona/ExpoIntelListView.vue'), meta: { title: '展会评估', requiresAuth: false, showFooter: true } },
  { path: '/expo-intel/:slug', name: 'expo-intel-detail', component: () => import('@/views/persona/ExpoIntelDetailView.vue'), meta: { title: '展会评估详情', requiresAuth: false, showFooter: true } },
  // 找展：自然语言一句话 → 结构化筛选 + 候选结果（入口页，比 /expo-intel 更省事）
  { path: '/expo-find', name: 'expo-find', component: () => import('@/views/persona/ExpoSearchView.vue'), meta: { title: '找展', requiresAuth: false, showFooter: true } },
  // V3.1: 展馆信息
  { path: '/venues', name: 'venue-list', component: () => import('@/views/VenueListView.vue'), meta: { title: '展馆名录', requiresAuth: false, showFooter: true } },
  { path: '/venues/:id', name: 'venue-detail', component: () => import('@/views/VenueDetailView.vue'), meta: { title: '展馆信息', requiresAuth: false, showFooter: true } },
  { path: '/booths/:id', name: 'booth-detail', component: () => import('@/views/booth/BoothDetailView.vue'), meta: { title: '展位详情', requiresAuth: false, showFooter: true } },
  { path: '/products', name: 'product-list', component: () => import('@/views/product/ProductListView.vue'), meta: { title: '展品列表', requiresAuth: false, showFooter: true } },
  { path: '/products/:id', name: 'product-detail', component: () => import('@/views/product/ProductDetailView.vue'), meta: { title: '展品详情', requiresAuth: false, showFooter: true } },
  // 展商名录 / 展品库（公开只读目录，数据来自 /catalog/*，无需登录）
  // 展商名录：对齐参考站 e.chtf.com/#/exhibitor 的信息架构（搜索 + 行业/城市/展会筛选 + 分页）
  { path: '/catalog/exhibitors', name: 'catalog-exhibitors', component: () => import('@/views/catalog/ExhibitorCatalogView.vue'), meta: { title: '展商名录', requiresAuth: false, showFooter: true } },
  { path: '/catalog/exhibitors/:id', name: 'catalog-exhibitor-detail', component: () => import('@/views/catalog/ExhibitorCatalogDetailView.vue'), meta: { title: '展商详情', requiresAuth: false, showFooter: true } },
  { path: '/catalog/products', name: 'catalog-products', component: () => import('@/views/catalog/ProductCatalogView.vue'), meta: { title: '展品库', requiresAuth: false, showFooter: true } },
  { path: '/catalog/products/:id', name: 'catalog-product-detail', component: () => import('@/views/catalog/ProductCatalogDetailView.vue'), meta: { title: '展品详情', requiresAuth: false, showFooter: true } },
  { path: '/procurements', name: 'procurement-list', component: () => import('@/views/procurement/ProcurementListView.vue'), meta: { title: '采购需求列表', requiresAuth: false, showFooter: true } },
  { path: '/procurements/:id', name: 'procurement-detail', component: () => import('@/views/procurement/ProcurementDetailView.vue'), meta: { title: '采购需求详情', requiresAuth: false, showFooter: true } },
  { path: '/search', name: 'search', component: () => import('@/views/search/SearchView.vue'), meta: { title: '搜索', requiresAuth: false, showFooter: true } },
  // V2.3: 微展位广场（公开）
  { path: '/micro-booths', name: 'micro-booth-list', component: () => import('@/views/MicroBoothPublicView.vue'), meta: { title: '微展位广场', requiresAuth: false, showFooter: true } },
  { path: '/micro-booths/:id', name: 'micro-booth-detail', component: () => import('@/views/MicroBoothPublicView.vue'), meta: { title: '微展位详情', requiresAuth: false, showFooter: true } },
  // 2026-10-19 合规：法律文本公开页（注册页勾选同意后跳转阅读；不设 roles，避免已登录用户被重定向）
  { path: '/privacy', name: 'privacy-policy', component: () => import('@/views/legal/PrivacyPolicyView.vue'), meta: { title: '隐私政策', requiresAuth: false, showFooter: true } },
  { path: '/terms', name: 'user-agreement', component: () => import('@/views/legal/UserAgreementView.vue'), meta: { title: '用户协议', requiresAuth: false, showFooter: true } },

  // ==================== 需登录（不限角色） ====================
  { path: '/messages', name: 'messages', component: () => import('@/views/message/MessageListView.vue'), meta: { title: '消息列表', requiresAuth: false, showFooter: true } },
  { path: '/messages/:id', name: 'conversation', component: () => import('@/views/message/ConversationView.vue'), meta: { title: '会话详情', requiresAuth: true, showFooter: false } },
  { path: '/profile', name: 'profile', component: () => import('@/views/user/ProfileView.vue'), meta: { title: '个人中心', requiresAuth: true, showFooter: true } },
  { path: '/settings', name: 'settings', component: () => import('@/views/user/SettingsView.vue'), meta: { title: '账户设置', requiresAuth: true, showFooter: true } },
  { path: '/points', name: 'points', component: () => import('@/views/visitor/PointsView.vue'), meta: { title: '商业积分', requiresAuth: false, showFooter: true } },
  { path: '/favorites', name: 'favorites', component: () => import('@/views/buyer/FavoritesView.vue'), meta: { title: '观展清单', requiresAuth: true, showFooter: true } },
  { path: '/notifications', name: 'notifications', component: () => import('@/views/NotificationListView.vue'), meta: { title: '通知', requiresAuth: true, showFooter: true } },

  // ==================== 观众 (visitor) ====================
  { path: '/visitor/registrations', name: 'visitor-registrations', component: () => import('@/views/visitor/MyRegistrationsView.vue'), meta: { title: '我的登记', requiresAuth: true, roles: ['visitor','buyer','exhibitor','admin'], showFooter: true } },
  // 我的采购 / 发布采购：全角色通用（后端 POST /procurements 明确"登录用户即可"）
  { path: '/visitor/procurements', name: 'visitor-procurements', component: () => import('@/views/visitor/MyProcurementsView.vue'), meta: { title: '我的采购', requiresAuth: true, roles: ['visitor','buyer','exhibitor','admin'], showFooter: true } },
  { path: '/visitor/procurements/create', name: 'visitor-procurement-create', component: () => import('@/views/visitor/ProcurementCreateView.vue'), meta: { title: '发布采购需求', requiresAuth: true, roles: ['visitor','buyer','exhibitor','admin'], showFooter: false } },

  // ==================== 买家 (buyer) ====================
  { path: '/buyer/dashboard', name: 'buyer-dashboard', component: () => import('@/views/buyer/DashboardView.vue'), meta: { title: '买家工作台', requiresAuth: true, roles: ['buyer'], showFooter: true } },
  { path: '/buyer/registrations', name: 'buyer-registrations', component: () => import('@/views/buyer/MyRegistrationsView.vue'), meta: { title: '我的报名', requiresAuth: true, roles: ['visitor','buyer','exhibitor','admin'], showFooter: true } },
  { path: '/buyer/procurements', name: 'buyer-procurements', component: () => import('@/views/buyer/MyProcurementsView.vue'), meta: { title: '我的采购', requiresAuth: true, roles: ['visitor','buyer','exhibitor','admin'], showFooter: true } },
  { path: '/buyer/procurements/create', name: 'buyer-procurement-create', component: () => import('@/views/buyer/ProcurementCreateView.vue'), meta: { title: '发布采购需求', requiresAuth: true, roles: ['visitor','buyer','exhibitor','admin'], showFooter: false } },

  // ==================== 参展商 (exhibitor) — 具体路由必须在 :id 通配之前 ====================
  { path: '/exhibitor/dashboard', name: 'exhibitor-dashboard', component: () => import('@/views/exhibitor/DashboardView.vue'), meta: { title: '参展商工作台', requiresAuth: true, roles: ['exhibitor'], showFooter: true } },
  { path: '/exhibitor/booths', name: 'exhibitor-booths', component: () => import('@/views/exhibitor/MyBoothsView.vue'), meta: { title: '我的展位', requiresAuth: true, roles: ['exhibitor'], showFooter: true } },
  { path: '/exhibitor/products', name: 'exhibitor-products', component: () => import('@/views/exhibitor/MyProductsView.vue'), meta: { title: '我的展品', requiresAuth: true, roles: ['exhibitor'], showFooter: true } },
  { path: '/exhibitor/products/create', name: 'exhibitor-product-create', component: () => import('@/views/exhibitor/ProductCreateView.vue'), meta: { title: '添加展品', requiresAuth: true, roles: ['exhibitor'], showFooter: false } },
  { path: '/exhibitor/products/:id/edit', name: 'exhibitor-product-edit', component: () => import('@/views/exhibitor/ProductEditView.vue'), meta: { title: '编辑展品', requiresAuth: true, roles: ['exhibitor'], showFooter: false } },
  { path: '/exhibitor/matches', name: 'exhibitor-matches', component: () => import('@/views/exhibitor/ProcurementMatchesView.vue'), meta: { title: '采购匹配', requiresAuth: true, roles: ['exhibitor'], showFooter: true } },
  { path: '/exhibitor/poster', name: 'exhibitor-poster', component: () => import('@/views/exhibitor/PosterView.vue'), meta: { title: '展商名片海报', requiresAuth: true, roles: ['exhibitor'], showFooter: false } },
  { path: '/exhibitor/micro-booth', name: 'exhibitor-micro-booth', component: () => import('@/views/exhibitor/MicroBoothView.vue'), meta: { title: '微展位管理', requiresAuth: true, roles: ['exhibitor'], showFooter: true } },
  { path: '/exhibitor/micro-booth/:id', name: 'exhibitor-micro-booth-detail', component: () => import('@/views/exhibitor/MicroBoothView.vue'), meta: { title: '微展位详情', requiresAuth: true, roles: ['exhibitor'], showFooter: true } },
  // 展商公开主页 — :id 通配必须放在最后
  { path: '/exhibitor/:id', name: 'exhibitor-profile', component: () => import('@/views/exhibitor/PublicProfileView.vue'), meta: { title: '展商主页', requiresAuth: false, showFooter: true } },

  // ==================== 平台自营展会管理（原主办方，2026-10-19 角色取消后归 admin） ====================
  { path: '/admin/dashboard', name: 'admin-dashboard', component: () => import('@/views/expo-admin/DashboardView.vue'), meta: { title: '平台运营工作台', requiresAuth: true, roles: ['admin'], showFooter: true } },
  { path: '/admin/venue-select', name: 'admin-venue-select', component: () => import('@/views/expo-admin/VenueSelectView.vue'), meta: { title: '展馆选择', requiresAuth: true, roles: ['admin'], showFooter: true } },
  { path: '/admin/exhibitions', name: 'admin-exhibitions', component: () => import('@/views/expo-admin/ExhibitionListView.vue'), meta: { title: '展会管理', requiresAuth: true, roles: ['admin'], showFooter: true } },
  { path: '/admin/exhibitions/create', name: 'admin-exhibition-create', component: () => import('@/views/expo-admin/ExhibitionCreateView.vue'), meta: { title: '创建展会', requiresAuth: true, roles: ['admin'], showFooter: false } },
  { path: '/admin/exhibitions/:id/edit', name: 'admin-exhibition-edit', component: () => import('@/views/expo-admin/ExhibitionEditView.vue'), meta: { title: '编辑展会', requiresAuth: true, roles: ['admin'], showFooter: false } },
  { path: '/admin/exhibitions/:id/booths', name: 'admin-booth-layout', component: () => import('@/views/expo-admin/BoothLayoutView.vue'), meta: { title: '展位布局', requiresAuth: true, roles: ['admin'], showFooter: true } },
  { path: '/admin/exhibitions/:id/booths/create', name: 'admin-booth-create', component: () => import('@/views/expo-admin/BoothCreateView.vue'), meta: { title: '创建展位', requiresAuth: true, roles: ['admin'], showFooter: false } },
  { path: '/admin/exhibitions/:id/booths/assign', name: 'admin-booth-assign', component: () => import('@/views/expo-admin/BoothAssignView.vue'), meta: { title: '分配展位', requiresAuth: true, roles: ['admin'], showFooter: false } },
  { path: '/admin/exhibitions/:id/registrations', name: 'admin-registrations', component: () => import('@/views/expo-admin/RegistrationsView.vue'), meta: { title: '观展登记', requiresAuth: true, roles: ['admin'], showFooter: true } },
  { path: '/admin/users', name: 'admin-users', component: () => import('@/views/expo-admin/UserManagementView.vue'), meta: { title: '用户管理', requiresAuth: true, roles: ['admin'], showFooter: true } },
  { path: '/admin/boss', name: 'boss-dashboard', component: () => import('@/views/admin/BossDashboard.vue'), meta: { title: 'Boss看板', requiresAuth: true, roles: ['admin'], showFooter: true } },

  // ==================== P3-P6 新功能（票务/现场/AI/平台） ====================
  { path: '/exhibitions/:id/tickets', name: 'ticket-shop', component: () => import('@/views/ticketing/TicketShopView.vue'), meta: { title: '购票', requiresAuth: false, showFooter: true } },
  { path: '/tickets/my', name: 'my-tickets', component: () => import('@/views/ticketing/MyTicketsView.vue'), meta: { title: '我的票务', requiresAuth: true, showFooter: true } },
  { path: '/admin/ticket-types', name: 'admin-ticket-types', component: () => import('@/views/expo-admin/TicketTypesView.vue'), meta: { title: '票种管理', requiresAuth: true, roles: ['admin'], showFooter: false } },
  { path: '/admin/onsite', name: 'admin-onsite', component: () => import('@/views/expo-admin/OnsiteConsoleView.vue'), meta: { title: '现场核销台', requiresAuth: true, roles: ['admin'], showFooter: false } },
  { path: '/admin/venues', name: 'admin-venues', component: () => import('@/views/admin/VenueManageView.vue'), meta: { title: '展馆管理', requiresAuth: true, roles: ['admin'], showFooter: false } },
  { path: '/admin/platform', name: 'admin-platform', component: () => import('@/views/admin/PlatformAdminView.vue'), meta: { title: '平台运营', requiresAuth: true, roles: ['admin'], showFooter: false } },
  { path: '/ai/lab', name: 'ai-lab', component: () => import('@/views/ai/AiLabView.vue'), meta: { title: 'AI 实验室', requiresAuth: true, showFooter: true } },

  // ==================== 404 ====================
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue'), meta: { title: '页面不存在', requiresAuth: false, showFooter: false } },
]

const router = createRouter({ history: createWebHistory(), routes, scrollBehavior() { return { top: 0 } } })

// 冷启动/刷新时 token 还���、但 Pinia 里的 profile 尚未拉取，
// 此时 userStore.role 是空字符串，若直接按角色判定会把已登录用户踢回首页。
// 这里用一个模块级 Promise 保证并发导航只补拉一次资料。
let profilePromise: Promise<unknown> | null = null

router.beforeEach(async (to, _from, next) => {
  document.title = `${to.meta.title || 'ExpoHub'} - ExpoHub`
  const userStore = useUserStore()
  const loggedIn = isLoggedIn() || userStore.isLoggedIn

  if (to.meta.requiresAuth === false) {
    if (loggedIn && to.meta.roles && (to.meta.roles as string[]).length === 0) {
      next(getRoleHomePath(userStore.role))
      return
    }
    next()
    return
  }

  if (!loggedIn) { next(`/login?redirect=${encodeURIComponent(to.fullPath)}`); return }

  // 已登录但角色为空（刷新/直接输入地址）→ 先补拉一次资料再判角色
  if (!userStore.role) {
    if (!profilePromise) {
      profilePromise = userStore.fetchProfile().catch(() => null).finally(() => { profilePromise = null })
    }
    await profilePromise
  }

  const routeRoles = to.meta.roles as string[] | undefined
  if (routeRoles && routeRoles.length > 0) {
    if (!routeRoles.includes(userStore.role)) {
      next(getRoleHomePath(userStore.role))
      return
    }
  }
  next()
})

export default router
