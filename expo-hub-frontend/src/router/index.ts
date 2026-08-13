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
  // V3.1: 展馆信息
  { path: '/venues/:id', name: 'venue-detail', component: () => import('@/views/VenueDetailView.vue'), meta: { title: '展馆信息', requiresAuth: false, showFooter: true } },
  { path: '/booths/:id', name: 'booth-detail', component: () => import('@/views/booth/BoothDetailView.vue'), meta: { title: '展位详情', requiresAuth: false, showFooter: true } },
  { path: '/products', name: 'product-list', component: () => import('@/views/product/ProductListView.vue'), meta: { title: '展品列表', requiresAuth: false, showFooter: true } },
  { path: '/products/:id', name: 'product-detail', component: () => import('@/views/product/ProductDetailView.vue'), meta: { title: '展品详情', requiresAuth: false, showFooter: true } },
  { path: '/procurements', name: 'procurement-list', component: () => import('@/views/procurement/ProcurementListView.vue'), meta: { title: '采购需求列表', requiresAuth: false, showFooter: true } },
  { path: '/procurements/:id', name: 'procurement-detail', component: () => import('@/views/procurement/ProcurementDetailView.vue'), meta: { title: '采购需求详情', requiresAuth: false, showFooter: true } },
  { path: '/search', name: 'search', component: () => import('@/views/search/SearchView.vue'), meta: { title: '搜索', requiresAuth: false, showFooter: true } },
  // V2.3: 微展位广场（公开）
  { path: '/micro-booths', name: 'micro-booth-list', component: () => import('@/views/MicroBoothPublicView.vue'), meta: { title: '微展位广场', requiresAuth: false, showFooter: true } },
  { path: '/micro-booths/:id', name: 'micro-booth-detail', component: () => import('@/views/MicroBoothPublicView.vue'), meta: { title: '微展位详情', requiresAuth: false, showFooter: true } },

  // ==================== 需登录（不限角色） ====================
  { path: '/messages', name: 'messages', component: () => import('@/views/message/MessageListView.vue'), meta: { title: '消息列表', requiresAuth: false, showFooter: true } },
  { path: '/messages/:id', name: 'conversation', component: () => import('@/views/message/ConversationView.vue'), meta: { title: '会话详情', requiresAuth: true, showFooter: false } },
  { path: '/profile', name: 'profile', component: () => import('@/views/user/ProfileView.vue'), meta: { title: '个人中心', requiresAuth: true, showFooter: true } },
  { path: '/settings', name: 'settings', component: () => import('@/views/user/SettingsView.vue'), meta: { title: '账户设置', requiresAuth: true, showFooter: true } },
  { path: '/points', name: 'points', component: () => import('@/views/visitor/PointsView.vue'), meta: { title: '商业积分', requiresAuth: false, showFooter: true } },
  { path: '/favorites', name: 'favorites', component: () => import('@/views/buyer/FavoritesView.vue'), meta: { title: '观展清单', requiresAuth: true, showFooter: true } },
  { path: '/notifications', name: 'notifications', component: () => import('@/views/NotificationListView.vue'), meta: { title: '通知', requiresAuth: true, showFooter: true } },

  // ==================== 观众 (visitor) ====================
  { path: '/visitor/registrations', name: 'visitor-registrations', component: () => import('@/views/visitor/MyRegistrationsView.vue'), meta: { title: '我的登记', requiresAuth: true, roles: ['visitor','buyer','exhibitor','organizer','admin'], showFooter: true } },
  { path: '/visitor/procurements', name: 'visitor-procurements', component: () => import('@/views/visitor/MyProcurementsView.vue'), meta: { title: '我的采购', requiresAuth: true, roles: ['visitor','buyer','exhibitor','organizer','admin'], showFooter: true } },
  { path: '/visitor/procurements/create', name: 'visitor-procurement-create', component: () => import('@/views/visitor/ProcurementCreateView.vue'), meta: { title: '发布采购需求', requiresAuth: true, roles: ['visitor'], showFooter: false } },

  // ==================== 买家 (buyer) ====================
  { path: '/buyer/dashboard', name: 'buyer-dashboard', component: () => import('@/views/buyer/DashboardView.vue'), meta: { title: '买家工作台', requiresAuth: true, roles: ['buyer'], showFooter: true } },
  { path: '/buyer/registrations', name: 'buyer-registrations', component: () => import('@/views/buyer/MyRegistrationsView.vue'), meta: { title: '我的报名', requiresAuth: true, roles: ['visitor','buyer','exhibitor','organizer','admin'], showFooter: true } },
  { path: '/buyer/procurements', name: 'buyer-procurements', component: () => import('@/views/buyer/MyProcurementsView.vue'), meta: { title: '我的采购', requiresAuth: true, roles: ['buyer'], showFooter: true } },
  { path: '/buyer/procurements/create', name: 'buyer-procurement-create', component: () => import('@/views/buyer/ProcurementCreateView.vue'), meta: { title: '发布采购需求', requiresAuth: true, roles: ['buyer'], showFooter: false } },

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

  // ==================== 主办方 (organizer) ====================
  { path: '/organizer/dashboard', name: 'organizer-dashboard', component: () => import('@/views/organizer/DashboardView.vue'), meta: { title: '主办方工作台', requiresAuth: true, roles: ['organizer','admin'], showFooter: true } },
  { path: '/organizer/exhibitions', name: 'organizer-exhibitions', component: () => import('@/views/organizer/ExhibitionListView.vue'), meta: { title: '展会管理', requiresAuth: true, roles: ['organizer','admin'], showFooter: true } },
  { path: '/organizer/exhibitions/create', name: 'organizer-exhibition-create', component: () => import('@/views/organizer/ExhibitionCreateView.vue'), meta: { title: '创建展会', requiresAuth: true, roles: ['organizer','admin'], showFooter: false } },
  { path: '/organizer/exhibitions/:id/edit', name: 'organizer-exhibition-edit', component: () => import('@/views/organizer/ExhibitionEditView.vue'), meta: { title: '编辑展会', requiresAuth: true, roles: ['organizer','admin'], showFooter: false } },
  { path: '/organizer/exhibitions/:id/booths', name: 'organizer-booth-layout', component: () => import('@/views/organizer/BoothLayoutView.vue'), meta: { title: '展位布局', requiresAuth: true, roles: ['organizer','admin'], showFooter: true } },
  { path: '/organizer/exhibitions/:id/booths/create', name: 'organizer-booth-create', component: () => import('@/views/organizer/BoothCreateView.vue'), meta: { title: '创建展位', requiresAuth: true, roles: ['organizer','admin'], showFooter: false } },
  { path: '/organizer/exhibitions/:id/booths/assign', name: 'organizer-booth-assign', component: () => import('@/views/organizer/BoothAssignView.vue'), meta: { title: '分配展位', requiresAuth: true, roles: ['organizer','admin'], showFooter: false } },
  { path: '/organizer/exhibitions/:id/registrations', name: 'organizer-registrations', component: () => import('@/views/organizer/RegistrationsView.vue'), meta: { title: '观展登记', requiresAuth: true, roles: ['organizer','admin'], showFooter: true } },
  { path: '/organizer/statistics', name: 'organizer-statistics', component: () => import('@/views/organizer/DashboardView.vue'), meta: { title: '数据统计', requiresAuth: true, roles: ['organizer','admin'], showFooter: true } },
  { path: '/organizer/users', name: 'organizer-users', component: () => import('@/views/organizer/UserManagementView.vue'), meta: { title: '用户管理', requiresAuth: true, roles: ['organizer','admin'], showFooter: true } },
  { path: '/admin/boss', name: 'boss-dashboard', component: () => import('@/views/admin/BossDashboard.vue'), meta: { title: 'Boss看板', requiresAuth: true, roles: ['admin'], showFooter: true } },

  // ==================== 404 ====================
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue'), meta: { title: '页面不存在', requiresAuth: false, showFooter: false } },
]

const router = createRouter({ history: createWebHistory(), routes, scrollBehavior() { return { top: 0 } } })

router.beforeEach((to, _from, next) => {
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
