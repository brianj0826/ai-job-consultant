<template>
  <RouterView v-if="route.meta.layout !== 'workspace'" v-slot="{ Component }">
    <Transition name="auth-shell" mode="out-in" appear>
      <component
        :is="Component"
        :key="route.fullPath"
        @login-success="handleLoginSuccess"
      />
    </Transition>
  </RouterView>

  <Transition v-else name="auth-shell" mode="out-in" appear>
    <div :key="workspaceIdentityKey" class="app-shell">
      <a class="skip-link" href="#main-content">跳至主要内容</a>

      <nav
        v-if="isTabletLayout"
        class="app-shell__rail"
        aria-label="快捷导航"
      >
        <button
          class="app-shell__rail-brand"
          type="button"
          aria-label="返回职业工作台"
          title="职业工作台"
          @click="handleGoHome"
        >
          <el-icon :size="22" aria-hidden="true"><Briefcase /></el-icon>
        </button>

        <div class="app-shell__rail-actions">
          <button
            class="app-shell__rail-button"
            :class="{ 'app-shell__rail-button--active': showDashboard && !isCareerWorkspace }"
            type="button"
            aria-label="职业工作台"
            title="职业工作台"
            @click="handleGoHome"
          >
            <el-icon :size="20" aria-hidden="true"><House /></el-icon>
          </button>
          <button
            ref="railNavigationButtonRef"
            class="app-shell__rail-button"
            :class="{ 'app-shell__rail-button--active': navigationOpen }"
            type="button"
            aria-label="打开导航"
            :aria-expanded="navigationOpen"
            aria-controls="app-navigation"
            title="打开导航"
            @click="toggleNavigation"
          >
            <el-icon :size="20" aria-hidden="true"><Menu /></el-icon>
          </button>
        </div>
      </nav>

      <Transition name="navigation-backdrop">
        <button
          v-if="isOverlayNavigation && navigationOpen"
          class="app-shell__backdrop"
          type="button"
          aria-label="关闭导航"
          @click="closeNavigation({ restoreFocus: true })"
        />
      </Transition>

      <aside
        id="app-navigation"
        ref="navigationRef"
        class="app-shell__sidebar"
        :class="{ 'app-shell__sidebar--open': navigationOpen }"
        :aria-hidden="isOverlayNavigation && !navigationOpen ? 'true' : undefined"
        :inert="isOverlayNavigation && !navigationOpen"
        aria-label="职业工作台导航"
        tabindex="-1"
        @transitionend="handleNavigationTransitionEnd"
      >
        <Sidebar
          ref="sidebarRef"
          :current-username="currentUsername"
          :user-id="currentUserId"
          :is-admin="auth.isAdmin.value"
          :preview-mode="isPreviewMode"
          :show-close-button="isOverlayNavigation"
          @session-changed="handleSidebarSessionChanged"
          @new-session="handleSidebarNewSession"
          @clear-session="handleSidebarClearSession"
          @pdf-uploaded="handleSidebarPdfUploaded"
          @show-analytics="handleShowAnalytics"
          @logout="handleLogout"
          @change-password="router.push({ name: 'change-password' })"
          @open-admin="router.push({ name: 'admin-overview' })"
          @quick-chat="handleSidebarQuickChat"
          @go-home="handleGoHome"
          @close-navigation="closeNavigation({ restoreFocus: true })"
        />
      </aside>

      <div class="app-shell__workspace">
        <AppTopbar
          ref="topbarRef"
          :title="pageTitle"
          :context="pageContext"
          :username="currentUsername"
          :navigation-open="navigationOpen"
          :view-key="activeViewKey"
          @toggle-navigation="toggleNavigation"
        />

        <main id="main-content" class="app-shell__main" tabindex="-1">
          <RouterView v-if="isCareerWorkspace" v-slot="{ Component }">
            <Transition name="workspace-view" mode="out-in">
              <component :is="Component" :key="route.name" />
            </Transition>
          </RouterView>
          <Transition v-else name="workspace-view" mode="out-in">
            <Dashboard
              v-if="showDashboard"
              key="dashboard"
              :username="currentUsername"
              @action="handleDashboardAction"
            />
            <ChatWindow
              v-else
              key="chat"
              :messages="messages"
              :session-id="currentSessionId"
              :session-status="sessionStatus"
              :session-error="sessionError"
              :user-id="currentUserId"
              :quick-text="quickChatText"
              @send-message="handleSendMessage"
              @kb-updated="sidebarRef?.loadDocStatus()"
              @retry-session="handleRetrySession"
              @request-document-upload="sidebarRef?.openDocumentPicker()"
            />
          </Transition>
        </main>
      </div>

      <AnalyticsPanel v-if="analyticsMounted" ref="analyticsPanelRef" :user-id="currentUserId" />
      <ResumeReport v-if="resumeMounted" ref="resumeReportRef" :report-text="lastAIResponse" />
      <JobMatchPanel v-if="jobMatchMounted" ref="jobMatchPanelRef" :report-text="lastAIResponse" />
    </div>
  </Transition>
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Briefcase, House, Menu } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { getErrorMessage, getMessages } from './api'
import {
  startAuthSynchronization,
  stopAuthSynchronization,
  useAuth
} from './composables/useAuth'
import { useDeferredPanel } from './composables/useDeferredPanel'
import { defaultRouteForUser, safeRedirectTarget } from './router'

const Sidebar = defineAsyncComponent(() => import('./components/Sidebar.vue'))
const AppTopbar = defineAsyncComponent(() => import('./components/AppTopbar.vue'))
const ChatWindow = defineAsyncComponent(() => import('./components/ChatWindow.vue'))
const Dashboard = defineAsyncComponent(() => import('./components/Dashboard.vue'))
const AnalyticsPanel = defineAsyncComponent(() => import('./components/AnalyticsPanel.vue'))
const ResumeReport = defineAsyncComponent(() => import('./components/ResumeReport.vue'))
const JobMatchPanel = defineAsyncComponent(() => import('./components/JobMatchPanel.vue'))

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const { currentUser, logout, setAuthenticatedUser } = auth
const isPreviewMode = computed(() => import.meta.env.DEV && route.query.preview === '1')
const workspaceIdentityKey = computed(() => (
  isPreviewMode.value ? 'workspace-preview' : `workspace-user-${currentUser.value?.id ?? 'anonymous'}`
))
const currentUsername = computed(() => isPreviewMode.value ? '体验用户' : (currentUser.value?.username || ''))
const messages = ref([])
const currentSessionId = ref(null)
const currentUserId = computed(() => isPreviewMode.value ? 0 : (currentUser.value?.id ?? null))
const sidebarRef = ref(null)
const navigationRef = ref(null)
const topbarRef = ref(null)
const railNavigationButtonRef = ref(null)

const showDashboard = ref(true)
const {
  componentRef: analyticsPanelRef,
  mounted: analyticsMounted,
  requestOpen: requestAnalyticsOpen
} = useDeferredPanel()
const {
  componentRef: resumeReportRef,
  mounted: resumeMounted,
  requestOpen: requestResumeOpen
} = useDeferredPanel()
const {
  componentRef: jobMatchPanelRef,
  mounted: jobMatchMounted,
  requestOpen: requestJobMatchOpen
} = useDeferredPanel()
const initialSessionReady = ref(false)
const sessionStatus = ref('idle')
const sessionError = ref('')
const lastAIResponse = ref('')
const quickChatText = ref('')
const lastQuickIntent = ref('')

const viewportWidth = ref(typeof window === 'undefined' ? 1440 : window.innerWidth)
const navigationOpen = ref(false)
const lastNavigationTrigger = ref(null)
const restoreNavigationFocusAfterLeave = ref(false)
let navigationFocusFallbackTimer = null
let sessionRequestId = 0

const isOverlayNavigation = computed(() => viewportWidth.value < 1280)
const isTabletLayout = computed(() => viewportWidth.value >= 768 && viewportWidth.value < 1280)
const isCareerWorkspace = computed(() => route.meta.workspaceSection === 'career')
const activeViewKey = computed(() => isCareerWorkspace.value
  ? String(route.name)
  : (showDashboard.value ? 'dashboard' : 'chat'))
const pageTitle = computed(() => route.meta.title
  || (showDashboard.value ? '职业工作台' : '职业智能对话'))
const pageContext = computed(() => route.meta.context
  || (showDashboard.value ? 'Career Intelligence Console' : '基于你的会话与知识库提供建议'))

const updateViewport = () => {
  viewportWidth.value = window.innerWidth
  if (!isOverlayNavigation.value) {
    navigationOpen.value = false
    restoreNavigationFocusAfterLeave.value = false
  }
}

const focusNavigation = () => {
  nextTick(() => navigationRef.value?.focus())
}

const openNavigation = (event) => {
  if (!isOverlayNavigation.value) return
  restoreNavigationFocusAfterLeave.value = false
  lastNavigationTrigger.value = event?.currentTarget || null
  navigationOpen.value = true
  focusNavigation()
}

const restoreNavigationFocus = () => {
  restoreNavigationFocusAfterLeave.value = false
  if (navigationFocusFallbackTimer) {
    clearTimeout(navigationFocusFallbackTimer)
    navigationFocusFallbackTimer = null
  }
  nextTick(() => {
    if (isTabletLayout.value) {
      railNavigationButtonRef.value?.focus()
    } else if (lastNavigationTrigger.value?.isConnected) {
      lastNavigationTrigger.value.focus()
    } else {
      topbarRef.value?.focusNavigationToggle?.()
    }
  })
}

const closeNavigation = ({ restoreFocus = false } = {}) => {
  if (!navigationOpen.value) return
  restoreNavigationFocusAfterLeave.value = restoreFocus
  navigationOpen.value = false
  if (!restoreFocus) return
  navigationFocusFallbackTimer = setTimeout(() => {
    if (restoreNavigationFocusAfterLeave.value) restoreNavigationFocus()
  }, 260)
}

const handleNavigationTransitionEnd = (event) => {
  if (
    event.target !== navigationRef.value ||
    event.propertyName !== 'transform' ||
    navigationOpen.value ||
    !restoreNavigationFocusAfterLeave.value
  ) return
  restoreNavigationFocus()
}

const toggleNavigation = (event) => {
  if (navigationOpen.value) {
    closeNavigation({ restoreFocus: true })
  } else {
    openNavigation(event)
  }
}

const handleKeydown = (event) => {
  if (event.defaultPrevented || event.key !== 'Escape' || !navigationOpen.value) return
  event.preventDefault()
  closeNavigation({ restoreFocus: true })
}

const handleDashboardAction = (routeName) => {
  if (routeName === 'chat') {
    showDashboard.value = false
    return
  }
  void router.push({ name: routeName })
}

const handleLoginSuccess = async (user) => {
  const authenticatedUser = setAuthenticatedUser(user)
  const redirect = safeRedirectTarget(route.query.redirect)
  if (authenticatedUser?.must_change_password) {
    await router.replace({ name: 'change-password' })
  } else if (redirect && redirect !== '/login') {
    await router.replace(redirect)
  } else {
    await router.replace(defaultRouteForUser(authenticatedUser))
  }
}

const resetWorkspace = () => {
  sessionRequestId += 1
  closeNavigation()
  messages.value = []
  currentSessionId.value = null
  sessionStatus.value = 'idle'
  sessionError.value = ''
  lastAIResponse.value = ''
  quickChatText.value = ''
  lastQuickIntent.value = ''
  showDashboard.value = true
  initialSessionReady.value = false
}

const handleLogout = async () => {
  if (!isPreviewMode.value) {
    try {
      await logout()
    } catch (error) {
      ElMessage.error(getErrorMessage(error, '退出登录失败，请检查网络后重试。'))
      return
    }
  }
  resetWorkspace()
  await router.replace({ name: 'login' })
}

watch(() => currentUser.value?.id ?? null, (nextUserId, previousUserId) => {
  if (nextUserId !== previousUserId) resetWorkspace()
})

watch(auth.lastRemoteAuthChange, (change) => {
  if (!change) return
  if (!auth.isAuthenticated.value) {
    if (route.meta.requiresAuth && route.name !== 'login') {
      void router.replace({ name: 'login', query: { redirect: route.fullPath } })
    }
    return
  }
  if (auth.mustChangePassword.value && route.name !== 'change-password') {
    void router.replace({ name: 'change-password' })
    return
  }
  if (route.meta.requiresAdmin && !auth.isAdmin.value) {
    void router.replace({ name: 'workspace' })
    return
  }
  if (route.name === 'login') {
    const redirect = safeRedirectTarget(route.query.redirect)
    void router.replace(redirect || defaultRouteForUser(currentUser.value))
    return
  }
  if (
    route.name === 'change-password'
    && !auth.mustChangePassword.value
    && ['login', 'register', 'change-password'].includes(change.reason)
  ) {
    void router.replace(defaultRouteForUser(currentUser.value))
  }
})

watch(isPreviewMode, (previewMode) => {
  if (previewMode) stopAuthSynchronization()
  else startAuthSynchronization()
}, { immediate: true })

const loadSessionMessages = async (sessionId, { navigate = true } = {}) => {
  const requestId = ++sessionRequestId
  currentSessionId.value = sessionId
  messages.value = []
  sessionError.value = ''
  sessionStatus.value = 'loading'
  if (navigate) {
    showDashboard.value = false
    if (route.name !== 'workspace') void router.push({ name: 'workspace' })
  }
  try {
    const res = await getMessages(sessionId)
    if (requestId !== sessionRequestId || currentSessionId.value !== sessionId) return
    messages.value = res.data.map(m => ({
      role: m.role,
      content: m.content,
      id: m.id,
      feedback: m.feedback,
      timestamp: m.timestamp
    }))
    sessionStatus.value = 'ready'
  } catch (e) {
    if (requestId !== sessionRequestId || currentSessionId.value !== sessionId) return
    sessionError.value = e.response?.data?.detail || '会话加载失败，请稍后重试。'
    sessionStatus.value = 'error'
  }
}

const handleSessionChanged = (sessionId) => {
  currentSessionId.value = sessionId
  if (!initialSessionReady.value) {
    initialSessionReady.value = true
    loadSessionMessages(sessionId, { navigate: false })
    return
  }
  loadSessionMessages(sessionId)
}

const handleRetrySession = (sessionId) => {
  const targetSessionId = sessionId || currentSessionId.value
  if (!targetSessionId || targetSessionId !== currentSessionId.value) return
  loadSessionMessages(targetSessionId)
}

const handleNewSession = (sessionId) => {
  sessionRequestId += 1
  currentSessionId.value = sessionId
  messages.value = []
  sessionError.value = ''
  sessionStatus.value = 'ready'
  if (!initialSessionReady.value) {
    initialSessionReady.value = true
    return
  }
  showDashboard.value = false
}

const handleClearSession = () => {
  sessionRequestId += 1
  currentSessionId.value = null
  messages.value = []
  sessionStatus.value = 'idle'
  sessionError.value = ''
  showDashboard.value = true
}

const handlePdfUploaded = () => {}

const handleSendMessage = (newMessages) => {
  messages.value = [...messages.value, ...newMessages]
  const last = newMessages[newMessages.length - 1]
  if (last?.role === 'assistant') lastAIResponse.value = last.content
}

const handleQuickChat = (text) => {
  if (route.name !== 'workspace') void router.push({ name: 'workspace' })
  showDashboard.value = false
  lastQuickIntent.value = text
  quickChatText.value = `${text} `
  nextTick(() => { quickChatText.value = '' })
}

const handleSidebarSessionChanged = (sessionId) => {
  closeNavigation({ restoreFocus: true })
  handleSessionChanged(sessionId)
}

const handleSidebarNewSession = (sessionId) => {
  closeNavigation({ restoreFocus: true })
  handleNewSession(sessionId)
}

const handleSidebarClearSession = () => {
  closeNavigation({ restoreFocus: true })
  handleClearSession()
}

const handleSidebarPdfUploaded = () => {
  closeNavigation({ restoreFocus: true })
  handlePdfUploaded()
}

const handleSidebarQuickChat = (text) => {
  closeNavigation({ restoreFocus: true })
  handleQuickChat(text)
}

const handleShowAnalytics = () => {
  closeNavigation()
  requestAnalyticsOpen()
}

const handleGoHome = () => {
  closeNavigation({ restoreFocus: true })
  showDashboard.value = true
  if (route.name !== 'workspace') void router.push({ name: 'workspace' })
}

watch(() => route.fullPath, () => {
  if (isCareerWorkspace.value) closeNavigation({ restoreFocus: true })
})

watch(lastAIResponse, (val) => {
  if (!val || !lastQuickIntent.value) return
  const intent = lastQuickIntent.value
  lastQuickIntent.value = ''
  if (intent.includes('分析简历') || val.includes('综合评分')) {
    requestResumeOpen()
  } else if (intent.includes('匹配') || val.includes('匹配度')) {
    requestJobMatchOpen()
  }
})

onMounted(() => {
  window.addEventListener('resize', updateViewport)
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  stopAuthSynchronization()
  if (navigationFocusFallbackTimer) clearTimeout(navigationFocusFallbackTimer)
  window.removeEventListener('resize', updateViewport)
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.auth-shell-enter-active {
  transition:
    opacity var(--duration-content, 220ms) var(--ease-enter, var(--ease-standard)),
    transform var(--duration-content, 220ms) var(--ease-enter, var(--ease-standard));
}

.auth-shell-leave-active {
  transition:
    opacity var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard)),
    transform var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard));
}

.auth-shell-enter-from,
.auth-shell-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.app-shell {
  position: relative;
  isolation: isolate;
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  height: 100dvh;
  min-height: 100dvh;
  overflow: clip;
  background:
    radial-gradient(circle at 58% -18%, var(--color-aurora-blue-soft), transparent 34rem),
    var(--color-canvas);
}

.app-shell::before {
  position: fixed;
  z-index: -1;
  inset: 0;
  background-image:
    linear-gradient(to right, var(--color-orbit) 1px, transparent 1px),
    linear-gradient(to bottom, var(--color-orbit) 1px, transparent 1px);
  background-size: 4rem 4rem;
  content: '';
  opacity: 0.16;
  pointer-events: none;
  -webkit-mask-image: linear-gradient(to bottom, var(--color-text-primary), transparent 62%);
  mask-image: linear-gradient(to bottom, var(--color-text-primary), transparent 62%);
}

.app-shell__sidebar {
  position: relative;
  grid-column: 1;
  z-index: var(--z-navigation);
  min-width: 0;
  height: 100dvh;
  padding: var(--space-5) var(--space-4) var(--space-4);
  overflow-y: auto;
  border-right: 1px solid var(--color-border-strong);
  background:
    linear-gradient(180deg, var(--color-aurora-violet-soft), transparent 8rem),
    var(--color-surface);
}

.app-shell__workspace {
  position: relative;
  grid-column: 2;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  height: 100dvh;
  min-width: 0;
  min-height: 100dvh;
}

.app-shell__main {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at 88% 8%, var(--color-aurora-cyan-soft), transparent 23rem),
    transparent;
}

.workspace-view-enter-active {
  transition:
    opacity var(--duration-content, 220ms) var(--ease-enter, var(--ease-standard)),
    transform var(--duration-content, 220ms) var(--ease-enter, var(--ease-standard));
}

.workspace-view-leave-active {
  transition:
    opacity var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard)),
    transform var(--duration-content-exit, 160ms) var(--ease-exit, var(--ease-standard));
}

.workspace-view-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.workspace-view-leave-to {
  opacity: 0;
  transform: translateY(-2px);
}

.navigation-backdrop-enter-active {
  transition: opacity var(--duration-backdrop, 180ms) var(--ease-enter, var(--ease-standard));
}

.navigation-backdrop-leave-active {
  transition: opacity var(--duration-backdrop, 180ms) var(--ease-exit, var(--ease-standard)) 40ms;
}

.navigation-backdrop-enter-from,
.navigation-backdrop-leave-to {
  opacity: 0;
}

.app-shell__rail,
.app-shell__backdrop {
  display: none;
}

@media (min-width: 1280px) {
  .app-shell__sidebar {
    position: sticky;
    top: 0;
  }
}

@media (min-width: 768px) and (max-width: 1279px) {
  .app-shell {
    grid-template-columns: var(--sidebar-width-compact) minmax(0, 1fr);
  }

  .app-shell__rail {
    position: sticky;
    top: 0;
    z-index: calc(var(--z-navigation) + 1);
    grid-column: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-8);
    height: 100dvh;
    padding: var(--space-5) var(--space-2);
    border-right: 1px solid var(--color-border-strong);
    background:
      linear-gradient(180deg, var(--color-aurora-violet-soft), transparent 9rem),
      var(--color-surface);
  }

  .app-shell__rail-brand,
  .app-shell__rail-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    padding: 0;
    border: 1px solid transparent;
    border-radius: var(--radius-control);
    background: transparent;
    color: var(--color-text-secondary);
    cursor: pointer;
    transition:
      color var(--duration-control) var(--ease-standard),
      border-color var(--duration-control) var(--ease-standard),
      background-color var(--duration-control) var(--ease-standard);
  }

  .app-shell__rail-brand {
    position: relative;
    overflow: hidden;
    border-color: color-mix(in srgb, var(--color-primary) 30%, var(--color-border));
    background: var(--color-primary-soft);
    color: var(--color-primary);
  }

  .app-shell__rail-brand::after {
    position: absolute;
    right: 0.35rem;
    bottom: 0.35rem;
    width: 0.3rem;
    height: 0.3rem;
    border-radius: var(--radius-pill);
    background: var(--color-cyan);
    box-shadow: 0 0 0.75rem var(--color-cyan);
    content: '';
  }

  .app-shell__rail-actions {
    display: grid;
    gap: var(--space-2);
  }

  .app-shell__rail-button:hover,
  .app-shell__rail-button--active,
  .app-shell__rail-brand:hover {
    border-color: color-mix(in srgb, var(--color-primary) 38%, var(--color-border));
    background: var(--color-primary-soft);
    color: var(--color-primary);
  }

  .app-shell__rail-button--active {
    box-shadow: inset 2px 0 var(--color-primary);
  }

  .app-shell__rail-brand:focus-visible,
  .app-shell__rail-button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }

  .app-shell__sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    left: var(--sidebar-width-compact);
    z-index: var(--z-navigation);
    width: min(var(--sidebar-width), calc(100dvw - var(--sidebar-width-compact)));
    height: 100dvh;
    border-right: 1px solid var(--color-border-strong);
    box-shadow: var(--shadow-dialog);
    transform: translateX(-100%);
    transition: transform var(--duration-panel-exit, 220ms) var(--ease-exit, var(--ease-standard));
  }

  .app-shell__sidebar--open {
    transform: translateX(0);
    transition-duration: var(--duration-panel, 300ms);
    transition-timing-function: var(--ease-enter, var(--ease-standard));
  }

  .app-shell__workspace {
    grid-column: 2;
  }

  .app-shell__backdrop {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    left: var(--sidebar-width-compact);
    z-index: var(--z-backdrop);
    display: block;
    padding: 0;
    border: 0;
    background:
      linear-gradient(90deg, var(--color-aurora-violet-soft), transparent 48%),
      var(--color-backdrop);
    cursor: pointer;
  }
}

@media (max-width: 767px) {
  .app-shell {
    display: block;
  }

  .app-shell__workspace {
    min-height: 100dvh;
  }

  .app-shell__sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    z-index: var(--z-navigation);
    width: 100vw;
    height: 100dvh;
    padding:
      max(var(--space-4), env(safe-area-inset-top))
      max(var(--space-4), env(safe-area-inset-right))
      max(var(--space-4), env(safe-area-inset-bottom))
      max(var(--space-4), env(safe-area-inset-left));
    border: 0;
    background:
      radial-gradient(circle at 12% 0, var(--color-aurora-violet-soft), transparent 17rem),
      var(--color-surface);
    box-shadow: var(--shadow-dialog);
    transform: translateX(-100%);
    transition: transform var(--duration-panel-exit, 220ms) var(--ease-exit, var(--ease-standard));
  }

  .app-shell__sidebar--open {
    transform: translateX(0);
    transition-duration: var(--duration-panel, 300ms);
    transition-timing-function: var(--ease-enter, var(--ease-standard));
  }

  .app-shell__backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-backdrop);
    display: block;
    padding: 0;
    border: 0;
    background:
      radial-gradient(circle at 0 0, var(--color-aurora-violet-soft), transparent 20rem),
      var(--color-backdrop);
    cursor: pointer;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-shell-enter-active,
  .auth-shell-leave-active,
  .workspace-view-enter-active,
  .workspace-view-leave-active,
  .navigation-backdrop-enter-active,
  .navigation-backdrop-leave-active,
  .app-shell__sidebar {
    transition-duration: 0.01ms;
    transition-delay: 0ms;
  }

  .auth-shell-enter-from,
  .auth-shell-leave-to,
  .workspace-view-enter-from,
  .workspace-view-leave-to {
    transform: none;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .app-shell__sidebar,
  .app-shell__rail,
  .app-shell__backdrop {
    background: var(--color-surface);
  }

  .app-shell__backdrop {
    background: var(--color-backdrop);
  }
}
</style>
