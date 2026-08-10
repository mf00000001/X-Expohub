import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { title: '天气查询平台' },
    },
    {
      path: '/city/:id',
      name: 'city-detail',
      component: () => import('@/views/CityDetailView.vue'),
      meta: { title: '城市详情' },
    },
    {
      path: '/search',
      name: 'search',
      component: () => import('@/views/SearchView.vue'),
      meta: { title: '搜索城市' },
    },
    {
      path: '/forecast/:id',
      name: 'forecast',
      component: () => import('@/views/ForecastView.vue'),
      meta: { title: '15日预报' },
    },
    {
      path: '/aqi/:id',
      name: 'aqi',
      component: () => import('@/views/AqiView.vue'),
      meta: { title: '空气质量' },
    },
    {
      path: '/map',
      name: 'map',
      component: () => import('@/views/MapView.vue'),
      meta: { title: '天气地图' },
    },
    {
      path: '/favorites',
      name: 'favorites',
      component: () => import('@/views/FavoritesView.vue'),
      meta: { title: '我的收藏', requiresAuth: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { title: '设置' },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录', guest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { title: '注册', guest: true },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      redirect: '/',
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  // 更新页面标题
  document.title = (to.meta.title as string) || '天气查询平台'

  // 需要登录的页面
  if (to.meta.requiresAuth) {
    const userStore = useUserStore()
    if (!userStore.isLoggedIn) {
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
  }

  // 仅游客可访问的页面（登录/注册）
  if (to.meta.guest) {
    const userStore = useUserStore()
    if (userStore.isLoggedIn) {
      return next({ name: 'home' })
    }
  }

  next()
})

export default router
