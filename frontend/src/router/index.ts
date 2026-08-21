import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Home',
      component: () => import('@/views/Home.vue'),
      // 游客可浏览；下单/收藏时再拦截
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
    },
    {
      path: '/cart',
      name: 'Cart',
      component: () => import('@/views/Cart.vue'),
      // 游客可看购物车；提交时拦截
    },
    {
      path: '/orders',
      name: 'Orders',
      component: () => import('@/views/Orders.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/profile',
      name: 'Profile',
      component: () => import('@/views/Profile.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/dishes/:id',
      name: 'DishDetail',
      component: () => import('@/views/DishDetail.vue'),
      // 游客可看菜品详情
    },
    {
      path: '/admin/dishes',
      name: 'DishManage',
      component: () => import('@/views/DishManage.vue'),
      meta: { requiresAuth: true, requiresFeeder: true },
    },
    {
      path: '/admin/categories',
      name: 'CategoryManage',
      component: () => import('@/views/CategoryManage.vue'),
      meta: { requiresAuth: true, requiresFeeder: true },
    },
    {
      path: '/admin/tags',
      name: 'TagManage',
      component: () => import('@/views/TagManage.vue'),
      meta: { requiresAuth: true, requiresFeeder: true },
    },
    {
      path: '/admin/users',
      name: 'UserManage',
      component: () => import('@/views/UserManage.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/orders/:id',
      name: 'OrderDetail',
      component: () => import('@/views/OrderDetail.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

// 路由守卫
router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('access_token')
  const userStore = useUserStore()

  // 1) 已登录用户访问 /login → 跳首页
  if (to.path === '/login' && token) {
    next('/')
    return
  }

  // 2) requiresAuth 路由：未登录跳 /login
  if (to.meta.requiresAuth && !token) {
    next('/login')
    return
  }

  // 3) 已登录但 user 未加载 → 拉一次
  if (token && !userStore.user) {
    await userStore.fetchUser()
  }

  // 4) 强制改密拦截：除 /profile 外所有路径都重定向到 /profile
  if (token && userStore.mustChangePassword && to.path !== '/profile') {
    next('/profile')
    return
  }

  // 5) 饲养员权限校验
  if (to.meta.requiresFeeder && !userStore.isFeeder) {
    next('/')
    return
  }

  // 6) 管理员权限校验
  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    next('/')
    return
  }

  next()
})

export default router
