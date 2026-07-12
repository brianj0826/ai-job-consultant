<template>
  <div class="admin-shell">
    <a class="admin-skip-link" href="#admin-main" @click.prevent="focusMainContent">跳到主要内容</a>
    <aside class="admin-sidebar" aria-label="管理员导航">
      <div class="admin-brand">
        <span class="admin-brand__mark" aria-hidden="true"><el-icon><DataAnalysis /></el-icon></span>
        <div class="admin-brand__copy">
          <strong>职达管理台</strong>
          <small>ADMIN CONTROL PLANE</small>
        </div>
      </div>

      <nav class="admin-nav">
        <RouterLink v-for="(item, index) in navigation" :key="item.to" :to="item.to">
          <span class="admin-nav__index" aria-hidden="true">0{{ index + 1 }}</span>
          <el-icon aria-hidden="true"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="admin-account">
        <div class="admin-account__identity">
          <strong>{{ currentUser?.username }}</strong>
          <span>{{ roleLabel }}</span>
        </div>
        <el-dropdown trigger="click">
          <el-button circle aria-label="账号操作"><el-icon><MoreFilled /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push({ name: 'workspace' })">个人工作台</el-dropdown-item>
              <el-dropdown-item @click="router.push({ name: 'change-password' })">修改密码</el-dropdown-item>
              <el-dropdown-item divided @click="signOut">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <div class="admin-workspace">
      <header class="admin-topbar">
        <div class="admin-topbar__title">
          <p class="technical-label">{{ route.meta.eyebrow || 'ADMINISTRATION' }}</p>
          <h1 id="admin-page-title">{{ route.meta.title || '管理控制台' }}</h1>
        </div>
        <el-tag effect="plain" :type="isSuperAdmin ? 'danger' : 'warning'">{{ roleLabel }}</el-tag>
      </header>
      <main id="admin-main" ref="mainContentRef" class="admin-main" tabindex="-1" aria-labelledby="admin-page-title">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  ChatDotRound,
  DataAnalysis,
  Document,
  MoreFilled,
  User
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { getErrorMessage } from '../api'
import { useAuth } from '../composables/useAuth'

const route = useRoute()
const router = useRouter()
const { currentUser, isSuperAdmin, logout } = useAuth()
const mainContentRef = ref(null)

const focusMainContent = () => {
  const main = mainContentRef.value
  if (!main) return
  main.focus({ preventScroll: true })
  main.scrollIntoView({ block: 'start' })
}

const navigation = [
  { to: '/admin/overview', label: '运行概览', icon: DataAnalysis },
  { to: '/admin/users', label: '用户管理', icon: User },
  { to: '/admin/feedback', label: '反馈审阅', icon: ChatDotRound },
  { to: '/admin/audit-logs', label: '审计日志', icon: Document }
]

const roleLabel = computed(() => isSuperAdmin.value ? '超级管理员' : '管理员')

const signOut = async () => {
  try {
    await logout()
    await router.replace({ name: 'login' })
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '退出登录失败，请检查网络后重试。'))
  }
}
</script>
