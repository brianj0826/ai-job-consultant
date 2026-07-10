<template>
  <WelcomePage
    v-if="!isLoggedIn"
    @login-success="handleLoginSuccess"
  />

  <div v-else class="app-shell">
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
          :class="{ 'app-shell__rail-button--active': showDashboard }"
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

    <button
      v-if="isOverlayNavigation && navigationOpen"
      class="app-shell__backdrop"
      type="button"
      aria-label="关闭导航"
      @click="closeNavigation()"
    />

    <aside
      id="app-navigation"
      ref="navigationRef"
      class="app-shell__sidebar"
      :class="{ 'app-shell__sidebar--open': navigationOpen }"
      :aria-hidden="isOverlayNavigation && !navigationOpen ? 'true' : undefined"
      :inert="isOverlayNavigation && !navigationOpen"
      aria-label="职业工作台导航"
      tabindex="-1"
    >
      <Sidebar
        ref="sidebarRef"
        :current-username="currentUsername"
        :user-id="currentUserId"
        @session-changed="handleSidebarSessionChanged"
        @new-session="handleSidebarNewSession"
        @clear-session="handleSidebarClearSession"
        @pdf-uploaded="handleSidebarPdfUploaded"
        @user-logged-in="handleUserLoggedIn"
        @show-analytics="handleShowAnalytics"
        @logout="handleLogout"
        @quick-chat="handleSidebarQuickChat"
        @go-home="handleGoHome"
      />
    </aside>

    <div class="app-shell__workspace">
      <AppTopbar
        ref="topbarRef"
        :title="pageTitle"
        :context="pageContext"
        :username="currentUsername"
        :navigation-open="navigationOpen"
        @toggle-navigation="toggleNavigation"
      />

      <main id="main-content" class="app-shell__main" tabindex="-1">
        <Dashboard
          v-if="showDashboard"
          :username="currentUsername"
          @action="handleDashboardAction"
        />
        <ChatWindow
          v-else
          :messages="messages"
          :session-id="currentSessionId"
          :user-id="currentUserId"
          :quick-text="quickChatText"
          @send-message="handleSendMessage"
          @kb-updated="sidebarRef?.loadDocStatus()"
        />
      </main>
    </div>

    <AnalyticsPanel ref="analyticsPanelRef" :user-id="currentUserId" />
    <ResumeReport ref="resumeReportRef" :report-text="lastAIResponse" />
    <JobMatchPanel ref="jobMatchPanelRef" :report-text="lastAIResponse" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Briefcase, House, Menu } from '@element-plus/icons-vue'
import WelcomePage from './components/WelcomePage.vue'
import Sidebar from './components/Sidebar.vue'
import AppTopbar from './components/AppTopbar.vue'
import ChatWindow from './components/ChatWindow.vue'
import AnalyticsPanel from './components/AnalyticsPanel.vue'
import ResumeReport from './components/ResumeReport.vue'
import JobMatchPanel from './components/JobMatchPanel.vue'
import Dashboard from './components/Dashboard.vue'
import { getMessages } from './api'

const isLoggedIn = ref(false)
const currentUsername = ref('')
const messages = ref([])
const currentSessionId = ref(null)
const currentUserId = ref(null)
const sidebarRef = ref(null)
const analyticsPanelRef = ref(null)
const resumeReportRef = ref(null)
const jobMatchPanelRef = ref(null)
const navigationRef = ref(null)
const topbarRef = ref(null)
const railNavigationButtonRef = ref(null)

const showDashboard = ref(true)
const initialSessionReady = ref(false)
const lastAIResponse = ref('')
const quickChatText = ref('')
const lastQuickIntent = ref('')

const viewportWidth = ref(typeof window === 'undefined' ? 1440 : window.innerWidth)
const navigationOpen = ref(false)
const lastNavigationTrigger = ref(null)

const isOverlayNavigation = computed(() => viewportWidth.value < 1280)
const isTabletLayout = computed(() => viewportWidth.value >= 768 && viewportWidth.value < 1280)
const pageTitle = computed(() => showDashboard.value ? '职业工作台' : '职业智能对话')
const pageContext = computed(() => showDashboard.value ? 'Career Intelligence Console' : '基于你的会话与知识库提供建议')

const updateViewport = () => {
  viewportWidth.value = window.innerWidth
  if (!isOverlayNavigation.value) navigationOpen.value = false
}

const focusNavigation = () => {
  nextTick(() => navigationRef.value?.focus())
}

const openNavigation = (event) => {
  if (!isOverlayNavigation.value) return
  lastNavigationTrigger.value = event?.currentTarget || null
  navigationOpen.value = true
  focusNavigation()
}

const closeNavigation = ({ restoreFocus = false } = {}) => {
  if (!navigationOpen.value) return
  navigationOpen.value = false
  if (!restoreFocus) return
  nextTick(() => {
    if (lastNavigationTrigger.value?.isConnected) {
      lastNavigationTrigger.value.focus()
    } else if (isTabletLayout.value) {
      railNavigationButtonRef.value?.focus()
    } else {
      topbarRef.value?.focusNavigationToggle?.()
    }
  })
}

const toggleNavigation = (event) => {
  if (navigationOpen.value) {
    closeNavigation({ restoreFocus: false })
  } else {
    openNavigation(event)
  }
}

const handleKeydown = (event) => {
  if (event.defaultPrevented || event.key !== 'Escape' || !navigationOpen.value) return
  event.preventDefault()
  closeNavigation({ restoreFocus: true })
}

const handleDashboardAction = (intent) => {
  showDashboard.value = false
  lastQuickIntent.value = intent
  quickChatText.value = `${intent} `
  nextTick(() => { quickChatText.value = '' })
}

const handleLoginSuccess = (userId, username) => {
  currentUserId.value = userId
  currentUsername.value = username
  isLoggedIn.value = true
}

const handleLogout = () => {
  closeNavigation()
  localStorage.removeItem('ai_user_id')
  localStorage.removeItem('ai_username')
  isLoggedIn.value = false
  currentUserId.value = null
  currentUsername.value = ''
  messages.value = []
  currentSessionId.value = null
  showDashboard.value = true
  initialSessionReady.value = false
}

const handleSessionChanged = async (sessionId) => {
  currentSessionId.value = sessionId
  if (!initialSessionReady.value) {
    initialSessionReady.value = true
    return
  }
  showDashboard.value = false
  try {
    const res = await getMessages(sessionId)
    messages.value = res.data.map(m => ({
      role: m.role,
      content: m.content,
      id: m.id,
      feedback: m.feedback,
      timestamp: m.timestamp
    }))
  } catch (e) {
    messages.value = []
  }
}

const handleNewSession = (sessionId) => {
  currentSessionId.value = sessionId
  messages.value = []
  if (!initialSessionReady.value) {
    initialSessionReady.value = true
    return
  }
  showDashboard.value = false
}

const handleClearSession = () => {
  currentSessionId.value = null
  messages.value = []
  showDashboard.value = true
}

const handlePdfUploaded = () => {}

const handleSendMessage = (newMessages) => {
  messages.value = [...messages.value, ...newMessages]
  const last = newMessages[newMessages.length - 1]
  if (last?.role === 'assistant') lastAIResponse.value = last.content
}

const handleUserLoggedIn = (id) => {
  currentUserId.value = id
}

const handleQuickChat = (text) => {
  showDashboard.value = false
  lastQuickIntent.value = text
  quickChatText.value = `${text} `
  nextTick(() => { quickChatText.value = '' })
}

const handleSidebarSessionChanged = (sessionId) => {
  closeNavigation()
  handleSessionChanged(sessionId)
}

const handleSidebarNewSession = (sessionId) => {
  closeNavigation()
  handleNewSession(sessionId)
}

const handleSidebarClearSession = () => {
  closeNavigation()
  handleClearSession()
}

const handleSidebarPdfUploaded = () => {
  closeNavigation()
  handlePdfUploaded()
}

const handleSidebarQuickChat = (text) => {
  closeNavigation()
  handleQuickChat(text)
}

const handleShowAnalytics = () => {
  closeNavigation()
  analyticsPanelRef.value?.open()
}

const handleGoHome = () => {
  closeNavigation()
  showDashboard.value = true
}

watch(lastAIResponse, (val) => {
  if (!val || !lastQuickIntent.value) return
  const intent = lastQuickIntent.value
  lastQuickIntent.value = ''
  if (intent.includes('分析简历') || val.includes('综合评分')) {
    nextTick(() => resumeReportRef.value?.open())
  } else if (intent.includes('匹配') || val.includes('匹配度')) {
    nextTick(() => jobMatchPanelRef.value?.open())
  }
})

onMounted(() => {
  const savedId = localStorage.getItem('ai_user_id')
  const savedName = localStorage.getItem('ai_username')
  if (savedId && savedName) {
    currentUserId.value = parseInt(savedId)
    currentUsername.value = savedName
    isLoggedIn.value = true
  }
  window.addEventListener('resize', updateViewport)
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateViewport)
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  min-height: 100dvh;
  overflow: clip;
  background: var(--color-canvas);
}

.app-shell__sidebar {
  grid-column: 1;
  z-index: var(--z-navigation);
  min-width: 0;
  height: 100dvh;
  padding: var(--space-4);
  overflow-y: auto;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
}

.app-shell__workspace {
  grid-column: 2;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
  min-height: 100dvh;
}

.app-shell__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--color-canvas);
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
    gap: var(--space-5);
    height: 100dvh;
    padding: var(--space-4) var(--space-2);
    border-right: 1px solid var(--color-border);
    background: var(--color-surface);
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
    color: var(--color-primary);
  }

  .app-shell__rail-actions {
    display: grid;
    gap: var(--space-2);
  }

  .app-shell__rail-button:hover,
  .app-shell__rail-button--active,
  .app-shell__rail-brand:hover {
    border-color: var(--color-border);
    background: var(--color-primary-soft);
    color: var(--color-primary);
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
    border-right: 1px solid var(--color-border);
    box-shadow: var(--shadow-dialog);
    transform: translateX(-100%);
    transition: transform var(--duration-panel) var(--ease-standard);
  }

  .app-shell__sidebar--open {
    transform: translateX(0);
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
    background: var(--color-backdrop);
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
    box-shadow: var(--shadow-dialog);
    transform: translateX(-100%);
    transition: transform var(--duration-panel) var(--ease-standard);
  }

  .app-shell__sidebar--open {
    transform: translateX(0);
  }

  .app-shell__backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-backdrop);
    display: block;
    padding: 0;
    border: 0;
    background: var(--color-backdrop);
    cursor: pointer;
  }
}
</style>
