import { createRouter, createWebHistory } from 'vue-router'
import {
  bootstrapAuth,
  clearAuth,
  markPasswordChangeRequired,
  useAuth
} from '../composables/useAuth'
import {
  setPasswordChangeRequiredHandler,
  setUnauthorizedHandler
} from '../api/client'

const WorkspaceRoute = { name: 'WorkspaceRoute', render: () => null }

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../components/WelcomePage.vue'),
    meta: { guestOnly: true, layout: 'standalone' }
  },
  {
    path: '/',
    name: 'workspace',
    component: WorkspaceRoute,
    meta: { requiresAuth: true, layout: 'workspace' }
  },
  {
    path: '/change-password',
    name: 'change-password',
    component: () => import('../views/ChangePasswordView.vue'),
    meta: { allowPasswordChange: true, layout: 'standalone', requiresAuth: true }
  },
  {
    path: '/forbidden',
    name: 'forbidden',
    component: () => import('../views/ForbiddenView.vue'),
    meta: { layout: 'standalone', requiresAuth: true }
  },
  {
    path: '/admin',
    component: () => import('../layouts/AdminLayout.vue'),
    redirect: { name: 'admin-overview' },
    meta: { layout: 'standalone', requiresAdmin: true, requiresAuth: true },
    children: [
      {
        path: 'overview',
        name: 'admin-overview',
        component: () => import('../views/admin/AdminOverviewView.vue'),
        meta: { title: '运行概览', eyebrow: 'ADMIN OVERVIEW' }
      },
      {
        path: 'users',
        name: 'admin-users',
        component: () => import('../views/admin/AdminUsersView.vue'),
        meta: { title: '用户管理', eyebrow: 'IDENTITY & ACCESS' }
      },
      {
        path: 'feedback',
        name: 'admin-feedback',
        component: () => import('../views/admin/AdminFeedbackView.vue'),
        meta: { title: '反馈审阅', eyebrow: 'QUALITY REVIEW' }
      },
      {
        path: 'audit-logs',
        name: 'admin-audit',
        component: () => import('../views/admin/AdminAuditView.vue'),
        meta: { title: '审计日志', eyebrow: 'PRIVILEGED ACTIVITY' }
      },
      {
        path: 'audit',
        redirect: { name: 'admin-audit' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: { name: 'workspace' }
  }
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

const isPreviewNavigation = (to) => (
  import.meta.env.DEV && to.name === 'workspace' && to.query.preview === '1'
)

export const safeRedirectTarget = (value) => {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return null
  const resolved = router.resolve(value)
  return resolved.matched.length ? value : null
}

export const defaultRouteForUser = (user) => {
  if (user?.must_change_password) return { name: 'change-password' }
  return ['admin', 'super_admin'].includes(user?.role)
    ? { name: 'admin-overview' }
    : { name: 'workspace' }
}

router.beforeEach(async (to) => {
  if (isPreviewNavigation(to)) return true

  const auth = useAuth()
  if (auth.authStatus.value === 'idle') {
    try {
      await bootstrapAuth()
    } catch {
      if (to.meta.requiresAuth) {
        return { name: 'login', query: { redirect: to.fullPath, unavailable: '1' } }
      }
    }
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (auth.isAuthenticated.value && auth.mustChangePassword.value && !to.meta.allowPasswordChange) {
    return { name: 'change-password' }
  }

  if (to.meta.guestOnly && auth.isAuthenticated.value) {
    return defaultRouteForUser(auth.currentUser.value)
  }

  if (to.meta.requiresAdmin && !auth.isAdmin.value) {
    return { name: 'forbidden' }
  }

  return true
})

setUnauthorizedHandler(() => {
  const currentRoute = router.currentRoute.value
  clearAuth()
  // During the initial /me probe, the navigation guard owns the redirect.
  // Redirecting from START_LOCATION would incorrectly inject redirect=/ into
  // an explicit /login navigation and send administrators to the user shell.
  if (!currentRoute.name || currentRoute.name === 'login') return
  router.replace({ name: 'login', query: { redirect: currentRoute.fullPath } })
})

setPasswordChangeRequiredHandler(() => {
  markPasswordChangeRequired()
  if (router.currentRoute.value.name !== 'change-password') {
    router.replace({ name: 'change-password' })
  }
})

export default router
