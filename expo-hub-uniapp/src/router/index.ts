import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    roles?: string[]
  }
}

const routes: RouteRecordRaw[] = [
  // ===== 公共页面（主包）=====
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/exhibitions',
    name: 'exhibition-list',
    component: () => import('@/views/ExhibitionListView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/exhibitions/:id',
    name: 'exhibition-detail',
    component: () => import('@/views/ExhibitionDetailView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/booths/:id',
    name: 'booth-detail',
    component: () => import('@/views/BoothDetailView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/products',
    name: 'product-list',
    component: () => import('@/views/ProductListView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/products/:id',
    name: 'product-detail',
    component: () => import('@/views/ProductDetailView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/procurements',
    name: 'procurement-list',
    component: () => import('@/views/ProcurementListView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/procurements/:id',
    name: 'procurement-detail',
    component: () => import('@/views/ProcurementDetailView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/messages',
    name: 'message-list',
    component: () => import('@/views/MessageListView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/messages/:id',
    name: 'message-conversation',
    component: () => import('@/views/MessageConversationView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ProfileView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('@/views/SearchView.vue'),
    meta: { requiresAuth: false },
  },

  // ===== 游客端 (Visitor) =====
  {
    path: '/visitor/registrations',
    name: 'visitor-registrations',
    component: () => import('@/views/visitor/MyRegistrationsView.vue'),
    meta: { requiresAuth: true, roles: ['visitor', 'buyer', 'exhibitor', 'organizer'] },
  },
  {
    path: '/visitor/procurements',
    name: 'visitor-procurements',
    component: () => import('@/views/visitor/MyProcurementsView.vue'),
    meta: { requiresAuth: true, roles: ['visitor', 'buyer', 'exhibitor', 'organizer'] },
  },
  {
    path: '/visitor/procurements/create',
    name: 'visitor-procurement-create',
    component: () => import('@/views/visitor/ProcurementCreateView.vue'),
    meta: { requiresAuth: true, roles: ['visitor', 'buyer', 'exhibitor', 'organizer'] },
  },

  // ===== 买家端 (Buyer) ★ =====
  {
    path: '/buyer/dashboard',
    name: 'buyer-dashboard',
    component: () => import('@/views/buyer/DashboardView.vue'),
    meta: { requiresAuth: true, roles: ['buyer'] },
  },
  {
    path: '/buyer/registrations',
    name: 'buyer-registrations',
    component: () => import('@/views/buyer/MyRegistrationsView.vue'),
    meta: { requiresAuth: true, roles: ['buyer'] },
  },
  {
    path: '/buyer/procurements',
    name: 'buyer-procurements',
    component: () => import('@/views/buyer/MyProcurementsView.vue'),
    meta: { requiresAuth: true, roles: ['buyer'] },
  },
  {
    path: '/buyer/procurements/create',
    name: 'buyer-procurement-create',
    component: () => import('@/views/visitor/ProcurementCreateView.vue'),
    meta: { requiresAuth: true, roles: ['buyer'] },
  },

  // ===== 展商端 (Exhibitor) =====
  {
    path: '/exhibitor/dashboard',
    name: 'exhibitor-dashboard',
    component: () => import('@/views/exhibitor/DashboardView.vue'),
    meta: { requiresAuth: true, roles: ['exhibitor'] },
  },
  {
    path: '/exhibitor/booths',
    name: 'exhibitor-booths',
    component: () => import('@/views/exhibitor/MyBoothsView.vue'),
    meta: { requiresAuth: true, roles: ['exhibitor'] },
  },
  {
    path: '/exhibitor/products',
    name: 'exhibitor-products',
    component: () => import('@/views/exhibitor/MyProductsView.vue'),
    meta: { requiresAuth: true, roles: ['exhibitor'] },
  },
  {
    path: '/exhibitor/products/create',
    name: 'exhibitor-product-create',
    component: () => import('@/views/exhibitor/ProductCreateView.vue'),
    meta: { requiresAuth: true, roles: ['exhibitor'] },
  },
  {
    path: '/exhibitor/products/:id/edit',
    name: 'exhibitor-product-edit',
    component: () => import('@/views/exhibitor/ProductCreateView.vue'),
    meta: { requiresAuth: true, roles: ['exhibitor'] },
  },
  {
    path: '/exhibitor/procurement-matches',
    name: 'exhibitor-procurement-matches',
    component: () => import('@/views/exhibitor/ProcurementMatchesView.vue'),
    meta: { requiresAuth: true, roles: ['exhibitor'] },
  },

  // ===== 主办方端 (Organizer) =====
  {
    path: '/organizer/dashboard',
    name: 'organizer-dashboard',
    component: () => import('@/views/organizer/DashboardView.vue'),
    meta: { requiresAuth: true, roles: ['organizer'] },
  },
  {
    path: '/organizer/exhibitions',
    name: 'organizer-exhibitions',
    component: () => import('@/views/organizer/ExhibitionListView.vue'),
    meta: { requiresAuth: true, roles: ['organizer'] },
  },
  {
    path: '/organizer/exhibitions/create',
    name: 'organizer-exhibition-create',
    component: () => import('@/views/organizer/ExhibitionCreateView.vue'),
    meta: { requiresAuth: true, roles: ['organizer'] },
  },
  {
    path: '/organizer/exhibitions/:id/edit',
    name: 'organizer-exhibition-edit',
    component: () => import('@/views/organizer/ExhibitionCreateView.vue'),
    meta: { requiresAuth: true, roles: ['organizer'] },
  },
  {
    path: '/organizer/exhibitions/:id/booth-layout',
    name: 'organizer-booth-layout',
    component: () => import('@/views/organizer/BoothCreateView.vue'),
    meta: { requiresAuth: true, roles: ['organizer'] },
  },
  {
    path: '/organizer/booths/create',
    name: 'organizer-booth-create',
    component: () => import('@/views/organizer/BoothCreateView.vue'),
    meta: { requiresAuth: true, roles: ['organizer'] },
  },
  {
    path: '/organizer/booths/:id/assign',
    name: 'organizer-booth-assign',
    component: () => import('@/views/organizer/BoothCreateView.vue'),
    meta: { requiresAuth: true, roles: ['organizer'] },
  },
  {
    path: '/organizer/registrations',
    name: 'organizer-registrations',
    component: () => import('@/views/organizer/RegistrationsView.vue'),
    meta: { requiresAuth: true, roles: ['organizer'] },
  },
  {
    path: '/organizer/statistics',
    name: 'organizer-statistics',
    component: () => import('@/views/organizer/StatisticsView.vue'),
    meta: { requiresAuth: true, roles: ['organizer'] },
  },

  // ===== 404 兜底 =====
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

// ===== 角色首页映射 =====
export const ROLE_HOME_MAP: Record<string, string> = {
  visitor: '/',
  buyer: '/buyer/dashboard',
  exhibitor: '/exhibitor/dashboard',
  organizer: '/organizer/dashboard',
}

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const userStore = useUserStore()

  // 未登录访问需授权页面 → 跳转登录
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }

  // 已登录访问登录/注册页 → 跳转角色首页
  if (userStore.isLoggedIn && (to.name === 'login' || to.name === 'register')) {
    const role = userStore.profile?.role || 'visitor'
    return next(ROLE_HOME_MAP[role] || '/')
  }

  // 角色权限检查
  if (to.meta.roles && to.meta.roles.length > 0) {
    const userRole = userStore.profile?.role
    if (userRole && !to.meta.roles.includes(userRole)) {
      showToast('您没有权限访问该页面', 'error')
      return next(ROLE_HOME_MAP[userRole] || '/')
    }
  }

  next()
})

function showToast(message: string, type: 'success' | 'error' | 'warning' = 'success') {
  const toast = document.createElement('div')
  toast.className = `toast toast-${type}`
  toast.textContent = message
  document.body.appendChild(toast)
  setTimeout(() => toast.remove(), 3000)
}

export default router
