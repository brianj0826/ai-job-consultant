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
    path: '/resumes',
    name: 'career-resumes',
    component: () => import('../views/career/CareerResourceView.vue'),
    props: { resource: 'resumes' },
    meta: {
      requiresAuth: true,
      layout: 'workspace',
      workspaceSection: 'career',
      title: '简历中心',
      context: '管理面向不同目标岗位的简历版本'
    }
  },
  {
    path: '/jobs',
    name: 'career-jobs',
    component: () => import('../views/career/CareerResourceView.vue'),
    props: { resource: 'jobs' },
    meta: {
      requiresAuth: true,
      layout: 'workspace',
      workspaceSection: 'career',
      title: '岗位库',
      context: '保存目标岗位与完整 JD'
    }
  },
  {
    path: '/applications',
    name: 'career-applications',
    component: () => import('../views/career/CareerResourceView.vue'),
    props: { resource: 'applications' },
    meta: {
      requiresAuth: true,
      layout: 'workspace',
      workspaceSection: 'career',
      title: '投递工作台',
      context: '跟进阶段、截止日期和下一步行动'
    }
  },
  {
    path: '/interviews',
    name: 'career-interviews',
    component: () => import('../views/career/CareerResourceView.vue'),
    props: { resource: 'interviews' },
    meta: {
      requiresAuth: true,
      layout: 'workspace',
      workspaceSection: 'career',
      title: '面试中心',
      context: '组织题目、回答、评分与复盘'
    }
  },
  {
    path: '/reports',
    name: 'career-reports',
    component: () => import('../views/career/CareerResourceView.vue'),
    props: { resource: 'reports' },
    meta: {
      requiresAuth: true,
      layout: 'workspace',
      workspaceSection: 'career',
      title: '报告中心',
      context: '查看持久化的结构化分析与复盘'
    }
  },
  {
    path: '/profile/skills',
    name: 'career-skills',
    component: () => import('../views/career/CareerResourceView.vue'),
    props: { resource: 'skills' },
    meta: {
      requiresAuth: true,
      layout: 'workspace',
      workspaceSection: 'career',
      title: '技能计划',
      context: '把岗位差距转化为可推进的成长任务'
    }
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
